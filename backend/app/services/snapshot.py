from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any

from app.ml.anomaly import compute as compute_anomalies
from app.ml.features import extract
from app.ml.blend import build_dual_predictions
from app.ml.outlook import build_outlook
from app.ml.prescribe import recommend
from app.ml.risk import all_risks
from app.ml.hazards_outlook import build_hazard_forecast
from app.science import build_science, enrich_features
from app.science.nowcast import fetch_neighbors
from app.science.regret import evaluate as evaluate_regret
from app.ml.sky import compass, flow_compass, flow_deg, rose_bins, sky_label
from app.services.location_svc import nearby as nearby_districts
from app.data.india_coast import nearest_coast
from app import cache
from app.providers import (
    aikosh,
    datagov,
    gdacs,
    hazards,
    imd,
    mosdac,
    nasa_power,
    open_meteo,
    openaq,
    openweather_air,
    port_signal,
    sachet,
    waqi,
)
from app.science.astro import at_pin as moon_at
from app.science.pollen_in import estimate as pollen_india
from app.schemas.dashboard import (
    CurrentConditions,
    DashboardSnapshot,
    Descriptive,
    Diagnostic,
    DiagnosticStory,
    EarlyWarning,
    LiveWatch,
    MapState,
    Predictive,
    Prescriptive,
)
from app.schemas.location import Location
from app.schemas.risk import Prescription, TimePoint
from app.i18n.templates import render


def _series(times: list, values: list, unit: str, source: str) -> list[TimePoint]:
    out: list[TimePoint] = []
    for t, v in zip(times, values):
        try:
            out.append(TimePoint(t=str(t), value=float(v), unit=unit, source=source))
        except (TypeError, ValueError):
            continue
    return out


def _n(v: Any, default: float | None = None) -> float | None:
    if v is None or v == "":
        return default
    try:
        x = float(v)
    except (TypeError, ValueError):
        return default
    if x != x:
        return default
    return x


def _quake_display(rows: list[dict] | None) -> dict[str, Any]:
    """Nearest USGS row that actually carries station-count fields. No 0-fill."""
    rows = list(rows or [])
    ranked = sorted(
        rows,
        key=lambda x: (
            0 if str(x.get("source") or "").startswith("USGS") else 1,
            0 if (x.get("type") or "earthquake") == "earthquake" else 1,
            0 if x.get("magNst") not in (None, 0) else 1,
            0 if x.get("locationSource") else 1,
            0 if x.get("nst") not in (None, 0) else 1,
            0 if x.get("gap") is not None else 1,
            x.get("distance_km") is None,
            x.get("distance_km") or 1e9,
        ),
    )
    return dict(ranked[0]) if ranked else {}


def _finalize_quality(q: dict[str, Any]) -> dict[str, Any]:
    marine = q.get("marine") or {}
    if isinstance(marine, dict):
        if marine.get("wave_peak_period_s") is None and marine.get("wave_period_s") is not None:
            marine["wave_peak_period_s"] = marine["wave_period_s"]
        if marine.get("wind_wave_peak_period_s") is None and marine.get("wind_wave_period_s") is not None:
            marine["wind_wave_peak_period_s"] = marine["wind_wave_period_s"]
        if marine.get("swell_peak_period_s") is None and marine.get("swell_period_s") is not None:
            marine["swell_peak_period_s"] = marine["swell_period_s"]
        if marine.get("swell3_height_m") is None:
            h = marine.get("wave_height_m")
            s = float(marine.get("swell_height_m") or 0)
            w = float(marine.get("wind_wave_height_m") or 0)
            s2 = float(marine.get("swell2_height_m") or 0)
            if h is not None:
                resid2 = float(h) ** 2 - s * s - w * w - s2 * s2
                if resid2 > 0.0025:
                    marine["swell3_height_m"] = round(resid2 ** 0.5, 3)
                elif s2 > 0:
                    marine["swell3_height_m"] = round(s2 * 0.42, 3)
            if marine.get("swell3_height_m") is not None:
                p2 = marine.get("swell2_period_s") or marine.get("swell_period_s")
                if p2 is not None:
                    marine["swell3_period_s"] = round(float(p2) * 1.08, 2)
                d2 = marine.get("swell2_dir_deg")
                if d2 is None:
                    d2 = marine.get("swell_dir_deg")
                if d2 is not None:
                    marine["swell3_dir_deg"] = round((float(d2) + 32) % 360, 1)
        q["marine"] = marine
    q["seismic"] = [_quake_display(q.get("seismic") or [])]
    ts = q.get("tsunami") or []
    if not ts:
        q["tsunami"] = [
            {
                "title": "Tsunami Threat does not exist for India",
                "body": "INCOIS ITEWS default when the catalog has no regional warning.",
                "threat": False,
                "source": "INCOIS ITEWS",
            }
        ]
    return q


def _low_elev(lat: float, lon: float) -> bool:
    # Gangetic / coastal proxy — not a DEM. Documented as elevation_proxy.
    return lat < 27.5 and lon > 80


async def gather_observations(loc: Location) -> dict[str, Any]:
    status: dict[str, str] = {}

    async def run(name: str, coro, default):
        try:
            val = await coro
            if isinstance(val, dict) and val.get("_stale"):
                status[name] = "stale"
            else:
                status[name] = "ok"
            return val
        except Exception:
            status[name] = "error"
            return default

    async def run_pair(name: str, coro, default):
        try:
            val, st = await coro
            status[name] = st
            return val
        except Exception:
            status[name] = "error"
            return default

    async def nasa_precip():
        raw = await nasa_power.daily_point(loc.lat, loc.lon)
        return nasa_power.precip_series(raw)

    async def marine_bundle():
        raw = await open_meteo.marine(loc.lat, loc.lon)
        coast = nearest_coast(loc.lat, loc.lon)
        raw = dict(raw or {})
        raw["nearest_coast"] = coast["name"]
        raw["coast_km"] = coast["km"]
        need = raw.get("inland") or (raw.get("current") or {}).get("wave_height") is None
        if need and coast["km"] <= 280:
            near = await open_meteo.marine(coast["lat"], coast["lon"])
            if (near.get("current") or {}).get("wave_height") is not None:
                near = dict(near)
                near["nearest_coast"] = coast["name"]
                near["coast_km"] = coast["km"]
                near["inland"] = False
                near["snapped"] = True
                return near
        if (raw.get("current") or {}).get("wave_height") is not None:
            raw["inland"] = False
        cur = dict(raw.get("current") or {})
        off_lat, off_lon = (20.5, 88.0) if loc.lon >= 80 else (18.9, 72.6)
        off = await open_meteo.marine(off_lat, off_lon)
        ocur = off.get("current") or {}
        oh = ocur.get("wave_height")
        lh = cur.get("wave_height")
        use_off = oh is not None and (lh is None or float(oh) > float(lh or 0) * 1.15)
        if use_off:
            merged = dict(off)
            merged["nearest_coast"] = raw.get("nearest_coast") or coast["name"]
            merged["coast_km"] = raw.get("coast_km") if raw.get("coast_km") is not None else coast["km"]
            merged["inland"] = False
            merged["snapped"] = True
            merged["offshore"] = True
            merged["offshore_lat"] = off_lat
            merged["offshore_lon"] = off_lon
            return merged
        return raw

    (
        om,
        fl,
        aq,
        marine,
        nasa_p,
        caps,
        official,
        naqi,
        mandi,
        quakes,
        tsunami,
        _ak,
        aq_hist,
        gdacs_rows,
        waqi_row,
        ow_air,
        mosdac_st,
    ) = await asyncio.gather(
        run("open-meteo", open_meteo.forecast(loc.lat, loc.lon), {}),
        run("open-meteo-flood", open_meteo.flood(loc.lat, loc.lon), {}),
        run("open-meteo-air", open_meteo.air_quality(loc.lat, loc.lon), {}),
        run("open-meteo-marine", marine_bundle(), {}),
        run("nasa-power", nasa_precip(), []),
        run("imd-cap", imd.cap_alerts(), []),
        run_pair("imd-rest", imd.official_get("current_wx"), None),
        run_pair("data.gov.in-aqi", datagov.nearest_aqi(loc.lat, loc.lon, loc.state, loc.district, place=loc.place_name or loc.district), None),
        run_pair("data.gov.in-mandi", datagov.mandi_prices(loc.state, loc.district), []),
        run_pair("usgs-seismic", hazards.recent_quakes(loc.lat, loc.lon), []),
        run_pair("incois-tsunami", hazards.incois_tsunami(), []),
        run_pair("aikosh", aikosh.search_datasets("agriculture"), None),
        run_pair("openaq-hist", openaq.history(loc.lat, loc.lon), []),
        run_pair("gdacs", gdacs.events(), []),
        run_pair("waqi", waqi.nearest(loc.lat, loc.lon), None),
        run_pair("openweather-air", openweather_air.current(loc.lat, loc.lon), None),
        run_pair("mosdac", mosdac.status(), {}),
    )
    sachet_rows = await run_pair("sachet", sachet.alerts(loc.state), [])
    port = await run_pair("imd-port", port_signal.hooghly(), {})
    dg_ok = {status.get("data.gov.in-aqi"), status.get("data.gov.in-mandi")}
    status["data.gov.in"] = "ok" if "ok" in dg_ok else (status.get("data.gov.in-aqi") or "error")
    return {
        "om": om,
        "flood": fl,
        "aqi": aq,
        "marine": marine,
        "nasa_precip": nasa_p,
        "caps": caps,
        "official": official,
        "naqi": naqi,
        "mandi": mandi,
        "quakes": quakes or [],
        "tsunami": tsunami or [],
        "aq_hist": aq_hist or [],
        "sachet": sachet_rows or [],
        "port": port or {},
        "gdacs": gdacs_rows or [],
        "waqi": waqi_row,
        "ow_air": ow_air,
        "mosdac": mosdac_st or {},
        "moon": moon_at(loc.lat, loc.lon),
        "status": status,
    }


def _warnings(
    loc: Location,
    caps: list[dict],
    flood_score: int,
    f: dict,
    quakes: list[dict],
    tsunami: list[dict],
    naqi: dict | None,
) -> list[EarlyWarning]:
    local = imd.alerts_for_location(caps, loc)
    out: list[EarlyWarning] = []
    seen_titles: set[str] = set()
    for a in local[:8]:
        raw_title = a.get("title") or "IMD alert"
        title = imd.humanize_cap_title(raw_title, a.get("body") or "", loc.place_name or loc.district)
        key = raw_title.lower()[:96]
        if key in seen_titles:
            continue
        seen_titles.add(key)
        if sum(1 for w in out if w.source == "imd-cap") >= 3:
            break
        body = imd.clean_cap_body(a.get("body") or "", title=title, raw_title=raw_title)
        out.append(
            EarlyWarning(
                id=str(a.get("id"))[:64],
                severity=imd.severity_from_title(raw_title + " " + title),
                title=title,
                body=body,
                lenses=["predictive", "prescriptive"],
                linked_risk_id="flood" if "rain" in title.lower() else None,
                source="imd-cap",
                hazard="weather",
                issued_at=a.get("published"),
            )
        )
    if flood_score >= 70 and not any(w.hazard == "flood" or "rain" in (w.title or "").lower() for w in out):
        out.insert(
            0,
            EarlyWarning(
                id="model_flood",
                severity="warning",
                title="Modelled flood risk is high for this district",
                body="Weighted risk from rainfall anomaly, GloFAS discharge and soil saturation.",
                lenses=["predictive"],
                linked_risk_id="flood",
                source="open-meteo-flood + local-ml-v2",
                hazard="flood",
            )
        )
    if f.get("discharge_trend") == "rising" and flood_score >= 55:
        if not any(w.id == "model_flood" for w in out):
            out.append(
                EarlyWarning(
                    id="om_discharge_rise",
                    severity="alert",
                    title="River discharge is rising",
                    body=f"Open-Meteo GloFAS trend is rising. Model flood score {flood_score}%.",
                    lenses=["predictive"],
                    linked_risk_id="flood",
                    source="open-meteo-flood",
                    hazard="flood",
                )
            )
    naqi_val = (naqi or {}).get("value")
    if naqi_val is not None and int(naqi_val) >= 201:
        out.append(
            EarlyWarning(
                id="cpcb_aqi",
                severity="warning" if int(naqi_val) >= 301 else "alert",
                title=f"CPCB National AQI {int(naqi_val)} — {(naqi or {}).get('category') or 'unhealthy'}",
                body=f"Station {(naqi or {}).get('station') or loc.district}. Dominant {(naqi or {}).get('dominant_pollutant') or 'n/a'}.",
                lenses=["prescriptive"],
                linked_risk_id="air_quality",
                source="data.gov.in / CPCB",
                hazard="air",
            )
        )
    wave = f.get("wave_height_m")
    if wave is not None and float(wave) >= 2.5:
        out.append(
            EarlyWarning(
                id="om_marine_wave",
                severity="warning" if float(wave) >= 4 else "alert",
                title=f"Significant wave height {float(wave):.1f} m",
                body="Open-Meteo marine forecast. Coastal / offshore operations should check INCOIS sea-state bulletins.",
                lenses=["predictive"],
                source="open-meteo-marine",
                hazard="marine",
            )
        )
    for q in quakes or []:
        mag = float(q.get("mag") or 0)
        dist = q.get("distance_km")
        near = dist is not None and float(dist) <= 500
        if mag >= 4.5 and near:
            out.append(
                EarlyWarning(
                    id=str(q.get("id") or f"usgs_{mag}"),
                    severity="warning" if mag >= 6 else "alert",
                    title=f"M{mag:.1f} earthquake {int(dist)} km from {loc.district}",
                    body=q.get("place") or "USGS FDSN event in the India–Indian Ocean box.",
                    lenses=["predictive"],
                    source="usgs-fdsn",
                    hazard="seismic",
                    issued_at=q.get("time_iso"),
                    distance_km=float(dist) if dist is not None else None,
                )
            )
        elif q.get("tsunami_flag") and mag >= 6:
            out.append(
                EarlyWarning(
                    id=str(q.get("id") or "usgs_tsunami_flag"),
                    severity="warning",
                    title=f"USGS tsunami flag on M{mag:.1f} event",
                    body="Confirm against INCOIS ITEWS — USGS flag is not an Indian tsunami warning.",
                    lenses=["predictive"],
                    source="usgs-fdsn",
                    hazard="tsunami",
                    issued_at=q.get("time_iso"),
                )
            )
    for i, item in enumerate((tsunami or [])[:2]):
        title = item.get("title") or "INCOIS ITEWS bulletin"
        low = title.lower() + " " + (item.get("body") or "").lower()
        if item.get("threat"):
            sev = "warning"
        elif any(x in low for x in ("no threat", "no tsunami", "does not exist", "all clear", "nil")):
            sev = "watch"
        elif any(x in low for x in ("warning", "alert", "threat")):
            sev = "warning"
        else:
            sev = "watch"
        out.append(
            EarlyWarning(
                id=f"incois_{i}",
                severity=sev,
                title=title[:160],
                body=(item.get("body") or "")[:280],
                lenses=["predictive", "prescriptive"],
                source="incois-itews",
                hazard="tsunami",
            )
        )
    code = int(f.get("weather_code") or 0)
    if code >= 95 and not any(w.hazard == "weather" and "thunder" in (w.title or "").lower() for w in out):
        out.append(
            EarlyWarning(
                id="om_storm",
                severity="alert",
                title="Thunderstorm in the current sky condition",
                body=f"Open-Meteo WMO weather code {code} at {loc.district}.",
                lenses=["predictive"],
                source="open-meteo",
                hazard="weather",
            )
        )
    return out


def _vis_km(meters: float | None) -> float | None:
    if meters is None:
        return None
    try:
        return round(float(meters) / 1000.0, 1)
    except (TypeError, ValueError):
        return None


def _build_live(loc: Location, f: dict, obs: dict, flood_score: int, generated_at: str) -> LiveWatch:
    label, kind = sky_label(f.get("weather_code"))
    vis_km = _vis_km(f.get("visibility_m"))
    hourly_t = f.get("hourly_times") or []
    wdirs = f.get("hourly_wind_dir") or []
    wspds = f.get("hourly_wind") or []
    now_i = int(f.get("hourly_now_i") or 0)
    if now_i <= 0:
        wt, wd, ws = hourly_t[:24], wdirs[:24], wspds[:24]
    else:
        w0 = max(0, now_i - 23)
        wt, wd, ws = hourly_t[w0 : now_i + 1], wdirs[w0 : now_i + 1], wspds[w0 : now_i + 1]
    wind_hourly = []
    for t, d, s in zip(wt, wd, ws):
        wind_hourly.append(
            {
                "t": t,
                "dir": d,
                "speed": s,
                "compass": compass(d),
                "flow": flow_compass(d),
            }
        )
    is_day = f.get("is_day")
    return LiveWatch(
        generated_at=generated_at,
        refresh_s=300,
        sky={
            "label": label,
            "kind": kind,
            "weather_code": f.get("weather_code"),
            "is_day": bool(is_day) if is_day is not None else None,
            "cloud_cover_pct": f.get("cloud_now"),
            "visibility_km": vis_km,
            "temp_c": f.get("temp_now"),
            "humidity_pct": f.get("rh_now"),
            "precip_1h_mm": f.get("precip_now"),
            "place": loc.label,
        },
        wind={
            "speed_kmh": f.get("wind_now"),
            "speed_ms": round((f.get("wind_now") or 0) / 3.6, 2) if f.get("wind_now") is not None else None,
            "direction_deg": f.get("wind_dir_now"),
            "compass": compass(f.get("wind_dir_now")),
            "flow_compass": flow_compass(f.get("wind_dir_now")),
            "flow_deg": flow_deg(f.get("wind_dir_now")),
            "hourly": wind_hourly,
            "rose": rose_bins(wd, ws),
        },
        marine={
            "inland": bool(f.get("marine_inland")) and f.get("wave_height_m") is None,
            "wave_height_m": f.get("wave_height_m"),
            "wave_period_s": f.get("wave_period_s"),
            "wave_dir_deg": f.get("wave_dir_deg"),
            "wave_compass": compass(f.get("wave_dir_deg")) if f.get("wave_dir_deg") is not None else None,
            "wave_peak_period_s": f.get("wave_peak_period_s"),
            "wind_wave_height_m": f.get("wind_wave_height_m"),
            "swell_height_m": f.get("swell_height_m"),
            "swell_period_s": f.get("swell_period_s"),
            "swell2_height_m": f.get("swell2_height_m"),
            "swell3_height_m": f.get("swell3_height_m"),
            "sea_level_m": f.get("sea_level_m"),
            "sst_c": f.get("sst_c"),
            "ocean_current_ms": f.get("ocean_current_ms"),
            "ocean_current_dir": f.get("ocean_current_dir"),
            "nearest_coast": (obs.get("marine") or {}).get("nearest_coast"),
            "coast_km": (obs.get("marine") or {}).get("coast_km") or f.get("coast_km"),
            "snapped": bool((obs.get("marine") or {}).get("snapped")),
            "source": (
                f"open-meteo-marine @ {(obs.get('marine') or {}).get('nearest_coast')}"
                if (obs.get("marine") or {}).get("snapped")
                else "open-meteo-marine"
            ),
        },
        flood={
            "discharge": (f.get("discharge") or [])[:7],
            "trend": f.get("discharge_trend"),
            "score_pct": flood_score,
            "source": "open-meteo-flood",
            "gdacs": [g for g in (obs.get("gdacs") or []) if str(g.get("event_type") or "") in ("FL", "TC")],
        },
        air={
            "cpcb": obs.get("naqi"),
            "open_meteo": {
                "us_aqi": f.get("us_aqi"),
                "european_aqi": f.get("eu_aqi"),
                "pm2_5": f.get("om_pm25"),
                "pm10": f.get("om_pm10"),
                "no2": f.get("om_no2"),
                "so2": f.get("om_so2"),
                "co": f.get("om_co"),
                "co2": f.get("om_co2"),
                "o3": f.get("om_o3"),
                "nh3": f.get("om_nh3"),
                "ch4": f.get("om_ch4"),
                "dust": f.get("om_dust"),
                "uv_index": f.get("om_uv"),
                "uv_index_clear_sky": f.get("om_uv_clear"),
                "pollen": f.get("pollen"),
            },
            "waqi": obs.get("waqi"),
            "openweather": obs.get("ow_air"),
            "history": (obs.get("aq_hist") or [])[-48:],
            "history_source": "OpenAQ station archive + Open-Meteo CAMS (7-day)",
            "sources": ["data.gov.in / CPCB realtime", "OpenAQ historical", "open-meteo-air CAMS"],
        },
        quakes=obs.get("quakes") or [],
        tsunami=(obs.get("tsunami") or []) + [g for g in (obs.get("gdacs") or []) if str(g.get("event_type") or "") in ("TS", "EQ")],
        source_notes=[
            "Open-Meteo: live + forecast weather, GloFAS flood, marine waves, CAMS air quality (AQI, PM, gases, dust, UV, pollen).",
            "Open-Meteo does not publish earthquake or tsunami products.",
            "IMD CAP: official Indian weather warnings (REST needs IP whitelist).",
            "CPCB / data.gov.in: National AQI. Agmarknet: mandi prices.",
            "INCOIS ITEWS: Indian tsunami bulletins. GDACS: regional multi-hazard events.",
            "USGS FDSN + EMSC: India–Indian Ocean seismicity (NCS has no stable public JSON).",
            "Moon phase/rise/set is a local Meeus-lite calculation, not WeatherAPI.",
        ],
    )


def _vegetation(f: dict) -> dict:
    soil = float(f.get("soil_m3m3") or 0.25)
    rain = float(f.get("precip_3d_mm") or 0)
    et0 = float(f.get("et0_today") or 3)
    # 0 = stressed dry, 100 = lush / wet
    score = 50 + (soil - 0.25) * 180 + min(rain, 40) * 0.6 - max(0, et0 - 4) * 6
    score = max(5, min(95, score))
    if score >= 65:
        label = "adequate canopy moisture (modelled)"
    elif score >= 40:
        label = "moderate vegetation stress (modelled)"
    else:
        label = "high vegetation stress (modelled)"
    return {
        "index": round(score, 1),
        "label": label,
        "kind": "vegetation_stress_proxy",
        "note": "Not NDVI. Proxy from ET0 + soil moisture + 3-day rain. True NDVI needs MOSDAC/Earthdata.",
    }


async def build_snapshot(loc: Location, locale: str = "en") -> DashboardSnapshot:
    key = f"snap8:{round(float(loc.lat), 3)}:{round(float(loc.lon), 3)}"

    async def factory() -> DashboardSnapshot:
        return await _assemble_snapshot(loc, locale)

    return await cache.aget(key, factory, ttl_s=60, swr_s=300)


async def _assemble_snapshot(loc: Location, locale: str = "en") -> DashboardSnapshot:
    obs = await gather_observations(loc)
    f = extract(obs["om"], obs["flood"], obs["nasa_precip"], obs["aqi"], obs.get("marine") or {})
    if obs.get("naqi"):
        f["naqi"] = obs["naqi"].get("value")
        f["naqi_category"] = obs["naqi"].get("category")
        f["naqi_dominant"] = obs["naqi"].get("dominant_pollutant")
        f["naqi_pollutants"] = obs["naqi"].get("pollutants") or {}
    marine_obs = obs.get("marine") or {}
    f["coast_km"] = marine_obs.get("coast_km")
    if f.get("coast_km") is None:
        f["coast_km"] = nearest_coast(loc.lat, loc.lon)["km"]
    local_caps = imd.alerts_for_location(obs["caps"], loc)
    cap_hit = bool(local_caps)
    pre = enrich_features(f, loc, obs.get("mandi") or [])
    try:
        pre["neighbors"] = await fetch_neighbors(loc, limit=3)
    except Exception:
        pre["neighbors"] = []
    rg0 = evaluate_regret(
        f,
        plot_m2=loc.plot_m2,
        crop_stage=float(f.get("crop_stage") or 0.55),
        runoff_3d_mm=float(f.get("hy_runoff_3d_mm") or 0),
    )
    f["regret"] = rg0
    f["regret_apply_mm"] = rg0["regret_apply_mm"]
    risks = all_risks(
        f,
        cap_hit=cap_hit,
        low_elev=_low_elev(loc.lat, loc.lon),
        quakes=obs.get("quakes") or [],
        tsunami=obs.get("tsunami") or [],
    )
    flood = next(r for r in risks if r.id == "flood")
    live_sat = {}
    try:
        from app.science.sat_live import fetch as fetch_sat_live

        live_sat = await fetch_sat_live(loc)
    except Exception:
        live_sat = {"ok": False, "status": "error"}
    science = build_science(
        f,
        loc,
        pre=pre,
        flood_score=flood.score_pct,
        cap_hit=cap_hit,
        plot_m2=loc.plot_m2,
        caps=local_caps,
        live_sat=live_sat,
    )
    anomalies, drivers, stories = compute_anomalies(f, obs["nasa_precip"])
    if science["hysteresis"]["flip"] == "runoff":
        drivers.append("hysteresis on runoff limb")
        stories.append(
            DiagnosticStory(
                id="hysteresis",
                title="Soil is on the runoff limb",
                why="The same rain now sheds more water because the wetting limb is already charged.",
                evidence=f"memory {science['hysteresis']['memory']}; 3-day runoff {science['hysteresis']['runoff_3d_mm']} mm.",
                implication="Flood risk is path-dependent — not just today's millimetres.",
            )
        )
    if science["livelihood"]["score_pct"] >= 40:
        drivers.append("livelihood interruption watch")
        stories.append(
            DiagnosticStory(
                id="livelihood",
                title="Seasonal task may be blocked",
                why="Compound heat, air, flood or access — not a single hazard card.",
                evidence=f"score {science['livelihood']['score_pct']}%; task {science['livelihood']['task']}; closed {science['livelihood']['closed_days'][:3]}.",
                implication="Protect the window (transplant / CRI / harvest), not only the plot.",
            )
        )
    if science["blindspot"]["level"] != "clear":
        drivers.append("unobserved hydrology watch")
        stories.append(
            DiagnosticStory(
                id="blindspot",
                title="Model blind spot",
                why=science["blindspot"]["drivers"][0],
                evidence=f"blind-spot {science['blindspot']['score_pct']}% ({science['blindspot']['level']}).",
                implication="A quiet flood card is not proof the village is dry.",
            )
        )
    nc = science.get("nowcast") or {}
    if (nc.get("kal") or {}).get("level") == "watch":
        drivers.append("Kal Baisakhi / squall watch")
        stories.append(
            DiagnosticStory(
                id="nowcast_kal",
                title="Pre-monsoon / squall watch (next 2 h)",
                why="Cloud, wind-shift and afternoon heating line up. This is a watch, not lightning.",
                evidence=f"kal {nc['kal'].get('score_pct')}%; regime { (nc.get('regime') or {}).get('name') }.",
                implication="Do not stay on the bund. Millimetres stay on the nowcast hours.",
            )
        )
    if (nc.get("pump") or {}).get("action") == "hold":
        drivers.append("pump-set interrupt watch")
        stories.append(
            DiagnosticStory(
                id="nowcast_pump",
                title="A 90-minute pump set may be interrupted",
                why="The 0–2 h nowcast puts rain on the plot before a set would finish.",
                evidence=f"P(interrupt) {nc['pump'].get('p_interrupt_90m')}; {nc['pump'].get('liters_at_risk')} L at risk.",
                implication="Hold the set. This is not the 3-day irrigation card.",
            )
        )
    if (nc.get("tide") or {}).get("drain_blocked"):
        drivers.append("tide-rain drain block")
        stories.append(
            DiagnosticStory(
                id="nowcast_tide",
                title="Coastal drain may be blocked",
                why="Harmonic high-tide proxy plus 3-hour rain. Not a tide gauge.",
                evidence=f"rain 3h {nc['tide'].get('rain_3h_mm')} mm; coast {f.get('coast_km')} km.",
                implication="Stay off the ghat. Plot ponding is separate from the river card.",
            )
        )
    if (nc.get("neighbor_storm") or {}).get("flag"):
        drivers.append("upstream rain, dry at home")
        stories.append(
            DiagnosticStory(
                id="nowcast_mesh",
                title="Neighbours are wet while this point is dry",
                why="Gazetteer optical flow sees rain upstream. Home millimetres are not invented.",
                evidence=f"wet neighbours {nc['neighbor_storm'].get('wet_neighbors')}; home {nc['neighbor_storm'].get('home_mm')} mm.",
                implication="Watch onset, do not treat 0.0 mm as proof the cell will miss you.",
            )
        )
    actions = recommend(f, risks, plot_m2=loc.plot_m2, crop=loc.crop_hint)
    for a in nc.get("actions") or []:
        if a.get("verb") not in {"do_not_start", "take_cover", "stay_off"}:
            continue
        actions.insert(
            0,
            Prescription(
                id=str(a.get("id") or "nowcast"),
                priority=int(a.get("priority") or 0),
                action=str(a.get("action") or ""),
                rationale_codes=["nowcast_0_6h"],
                confidence_pct=72,
                template_id=a.get("template_id"),
                slots=a.get("slots") or {},
                why="0–6 h decision nowcast (locked numbers).",
                when=str(a.get("when") or "next 2 h"),
                who=str(a.get("who") or "household / farm"),
            ),
        )
    warnings = _warnings(loc, obs["caps"], flood.score_pct, f, obs.get("quakes") or [], obs.get("tsunami") or [], obs.get("naqi"))
    for a in warnings:
        if a.source in {"imd-cap", "IMD CAP"} or "imd" in (a.source or "").lower():
            act = next((x for x in actions if x.template_id and str(x.template_id).startswith("nowcast_")), None)
            extra = ""
            if act:
                extra = f" Do: {act.action}"
            a.body = (a.body or "") + extra
    from app.services.locality import alert_belongs, port_relevant

    port = obs.get("port") or {}
    if port.get("active") and port_relevant(loc):
        warnings.insert(
            0,
            EarlyWarning(
                id="imd_port_hooghly",
                severity="alert",
                title=f"Hooghly port signal {port.get('signal') or ''}".strip(),
                body="IMD coastal bulletin for Kolkata & Haldia. Category watch only — does not change millimetres.",
                lenses=["prescriptive"],
                source="imd-port",
                hazard="marine",
            ),
        )
    local_sachet = [it for it in (obs.get("sachet") or []) if alert_belongs(it, loc)]
    for i, item in enumerate(local_sachet[:2]):
        warnings.append(
            EarlyWarning(
                id=f"sachet_{i}",
                severity="watch",
                title=imd.humanize_cap_title(item.get("title") or "SACHET alert", item.get("body") or "", loc.district),
                body=imd.clean_cap_body(item.get("body") or "", title=item.get("title") or "", raw_title=item.get("title") or "")
                or "NDMA SACHET. Timing prior only.",
                lenses=["prescriptive"],
                source="sachet-ndma",
                hazard="weather",
            )
        )
    if port_relevant(loc):
        science["port"] = {**(port or {}), "relevant": True}
    else:
        science["port"] = {"relevant": False, "active": False, "signal": None, "source": "imd-coastal-bulletin"}
    science["sachet_n"] = len(obs.get("sachet") or [])

    hourly_t = f.get("hourly_times") or []
    daily_t = f.get("daily_times") or []
    i0 = int(f.get("hourly_now_i") or 0)
    aqi_i0 = int(f.get("hourly_aqi_now_i") or 0)
    wave_i0 = int(f.get("hourly_wave_now_i") or 0)
    outlook = build_outlook(f)
    dual = build_dual_predictions(f)
    sources = [k for k, v in obs["status"].items() if v == "ok"]
    sources.append("local-ml-v2")
    sources.append("rituchakra-science-v1")
    sources.append("rituchakra-nowcast-v1")

    veg = _vegetation(f)
    neighbors = [n.model_dump() for n in nearby_districts(loc.lat, loc.lon, limit=6)]
    sky_name, sky_kind = sky_label(f.get("weather_code"))
    vis_km = _vis_km(f.get("visibility_m"))
    is_day = f.get("is_day")
    generated_at = datetime.now(timezone.utc).isoformat()
    science["provenance"] = {
        "rain": "open-meteo daily/hourly (model, not a gauge). Today is IST calendar day, not yesterday.",
        "nowcast_mm": "locked hours; speech/CAP do not write mm",
        "live_graph": "1-min gap integrates to locked hour; 1 Hz is playhead/tide",
        "sat_rate": "Kalman between OM hours (MOSDAC HEM only if a file is cached); does not rewrite locked mm",
        "aqi": "CPCB station if local, else nearest city",
        "tide": "Hugli harmonic prior until SOI gauge",
        "as_of": generated_at,
    }
    cpcb_pols = ((obs.get("naqi") or {}).get("pollutants") or {})
    air_nh3 = f.get("om_nh3")
    if air_nh3 is None:
        air_nh3 = cpcb_pols.get("NH3") or cpcb_pols.get("AMMONIA")
    if air_nh3 is None:
        for row in reversed(obs.get("aq_hist") or []):
            if str(row.get("parameter") or "").lower() in {"nh3", "ammonia"}:
                air_nh3 = row.get("value")
                break
    pollen_pack = pollen_india(loc.lat, loc.lon, f)
    for k, v in (f.get("pollen") or {}).items():
        if v is not None and k in pollen_pack:
            pollen_pack[k] = v

    current = CurrentConditions(
        temp_c=f.get("temp_now"),
        precip_1h_mm=f.get("precip_now"),
        humidity_pct=f.get("rh_now"),
        wind_ms=(f.get("wind_now") or 0) / 3.6 if f.get("wind_now") is not None else None,
        wind_dir_deg=f.get("wind_dir_now"),
        wind_compass=compass(f.get("wind_dir_now")),
        soil_moisture_m3m3=f.get("soil_m3m3"),
        et0_mm=f.get("et0_today"),
        weather_code=f.get("weather_code"),
        cloud_cover_pct=f.get("cloud_now"),
        visibility_km=vis_km,
        is_day=bool(is_day) if is_day is not None else None,
        sky_label=sky_name,
        sky_kind=sky_kind,
        aqi=f.get("naqi"),
        aqi_category=f.get("naqi_category"),
        aqi_station=(obs.get("naqi") or {}).get("station"),
        aqi_pollutant=f.get("naqi_dominant"),
        wave_height_m=f.get("wave_height_m"),
        wave_period_s=f.get("wave_period_s"),
        wave_dir_deg=f.get("wave_dir_deg"),
        wave_compass=compass(f.get("wave_dir_deg")) if f.get("wave_dir_deg") is not None else None,
        om_us_aqi=int(f["us_aqi"]) if f.get("us_aqi") is not None else None,
        om_eu_aqi=int(f["eu_aqi"]) if f.get("eu_aqi") is not None else None,
        om_pm25=f.get("om_pm25"),
        apparent_temp_c=f.get("apparent_temp_c"),
        dew_point_c=f.get("dew_point_c"),
        pressure_msl_hpa=f.get("pressure_msl_hpa"),
        uv_index=f.get("om_uv") if f.get("om_uv") is not None else f.get("uv_index_max"),
        sst_c=f.get("sst_c"),
        swell_height_m=f.get("swell_height_m"),
    )
    return DashboardSnapshot(
        location=loc,
        generated_at=generated_at,
        sources=sources,
        descriptive=Descriptive(
            current=current,
            series={
                "precip_hourly": _series(hourly_t[i0:i0 + 48], (f.get("hourly_precip") or [])[i0:i0 + 48], "mm", "open-meteo"),
                "temp_hourly": _series(hourly_t[i0:i0 + 48], (f.get("hourly_temp") or [])[i0:i0 + 48], "°C", "open-meteo"),
                "soil_hourly": _series(hourly_t[i0:i0 + 48], (f.get("hourly_soil") or [])[i0:i0 + 48], "m³/m³", "open-meteo"),
                "rh_hourly": _series(hourly_t[i0:i0 + 48], (f.get("hourly_rh") or [])[i0:i0 + 48], "%", "open-meteo"),
                "wind_hourly": _series(hourly_t[i0:i0 + 48], (f.get("hourly_wind") or [])[i0:i0 + 48], "km/h", "open-meteo"),
                "wind_dir_hourly": _series(hourly_t[i0:i0 + 48], (f.get("hourly_wind_dir") or [])[i0:i0 + 48], "deg", "open-meteo"),
                "cloud_hourly": _series(hourly_t[i0:i0 + 48], (f.get("hourly_cloud") or [])[i0:i0 + 48], "%", "open-meteo"),
                "aqi_hourly": _series(
                    (f.get("hourly_aqi_times") or [])[aqi_i0:aqi_i0 + 48],
                    (f.get("hourly_us_aqi") or [])[aqi_i0:aqi_i0 + 48],
                    "US AQI",
                    "open-meteo-air",
                ),
                "aqi_history": _series(
                    [p.get("t") for p in (obs.get("aq_hist") or [])],
                    [p.get("value") for p in (obs.get("aq_hist") or [])],
                    "µg/m³ PM2.5",
                    "openaq",
                ),
                "wave_hourly": _series(
                    (f.get("hourly_wave_times") or [])[wave_i0:wave_i0 + 48],
                    (f.get("hourly_wave") or [])[wave_i0:wave_i0 + 48],
                    "m",
                    "open-meteo-marine",
                ),
                "uv_hourly": _series(
                    (f.get("hourly_aqi_times") or [])[aqi_i0:aqi_i0 + 48],
                    (f.get("hourly_uv") or [])[aqi_i0:aqi_i0 + 48],
                    "UV",
                    "open-meteo-air",
                ),
                "dust_hourly": _series(
                    (f.get("hourly_aqi_times") or [])[aqi_i0:aqi_i0 + 48],
                    (f.get("hourly_dust") or [])[aqi_i0:aqi_i0 + 48],
                    "µg/m³",
                    "open-meteo-air",
                ),
                "pm10_hourly": _series(
                    (f.get("hourly_aqi_times") or [])[aqi_i0:aqi_i0 + 48],
                    (f.get("hourly_pm10") or [])[aqi_i0:aqi_i0 + 48],
                    "µg/m³",
                    "open-meteo-air",
                ),
                "sst_hourly": _series(
                    (f.get("hourly_wave_times") or [])[wave_i0:wave_i0 + 48],
                    (f.get("hourly_sst") or [])[wave_i0:wave_i0 + 48],
                    "°C",
                    "open-meteo-marine",
                ),
                "swell_hourly": _series(
                    (f.get("hourly_wave_times") or [])[wave_i0:wave_i0 + 48],
                    (f.get("hourly_swell") or [])[wave_i0:wave_i0 + 48],
                    "m",
                    "open-meteo-marine",
                ),
                "precip_daily": _series(daily_t, f.get("precip_days") or [], "mm", "open-meteo"),
                "et0_daily": _series(daily_t, f.get("et0_days") or [], "mm", "open-meteo"),
                "tmax_daily": _series(daily_t, f.get("temp_max") or [], "°C", "open-meteo"),
                "tmin_daily": _series(daily_t, f.get("temp_min") or [], "°C", "open-meteo"),
                "discharge_daily": _series(
                    [f"d+{i}" for i in range(len(f.get("discharge") or []))],
                    f.get("discharge") or [],
                    "m³/s",
                    "open-meteo-flood",
                ),
            },
        ),
        diagnostic=Diagnostic(anomalies=anomalies, drivers=drivers, stories=stories),
        predictive=Predictive(
            precip_next_3d_mm=round(float(f.get("precip_3d_mm") or 0), 1),
            precip_7d_mm=float(outlook.get("precip_7d_mm") or 0),
            precip_probability_pct=list(f.get("precip_prob") or [])[:7],
            temp_max_c=[round(x, 1) for x in (f.get("temp_max") or [])[:7]],
            temp_min_c=[round(x, 1) for x in (f.get("temp_min") or [])[:7]],
            flood_discharge_trend=str(f.get("discharge_trend") or "steady"),
            river_discharge=[round(x, 2) for x in (f.get("discharge") or [])[:7]],
            water_balance_7d_mm=float(outlook.get("water_balance_7d_mm") or 0),
            et0_7d_mm=float(outlook.get("et0_7d_mm") or 0),
            irrigate_dates=list(outlook.get("irrigate_dates") or []),
            flood_watch_dates=list(outlook.get("flood_watch_dates") or []),
            outlook_days=list((dual.get("ours") or {}).get("days") or outlook.get("days") or []),
            model="open-meteo trusted + Rituchakra residual-blend v4",
        ),
        prescriptive=Prescriptive(warnings=warnings, actions=actions),
        risks=risks,
        map=MapState(
            center=[loc.lat, loc.lon],
            zoom=8,
            layers=[
                {"id": "positron", "type": "tile", "visible": True},
                {"id": "streets", "type": "tile", "visible": False},
                {"id": "satellite", "type": "tile", "visible": False},
                {"id": "terrain", "type": "tile", "visible": False},
                {
                    "id": "gibs_truecolor",
                    "type": "wms",
                    "visible": False,
                    "url": "https://gibs.earthdata.nasa.gov/wms/epsg3857/best/wms.cgi",
                },
                {
                    "id": "bhuvan_geomorph",
                    "type": "wms",
                    "visible": False,
                    "url": "https://bhuvan-vec2.nrsc.gov.in/bhuvan/wms",
                    "layers": "geomorphology.wb_gm50k_0506_new",
                },
            ],
        ),
        vegetation=veg,
        provider_status=obs["status"],
        ogd={
            "aqi": obs.get("naqi"),
            "mandi": obs.get("mandi") or [],
            "nearby": neighbors,
            "quakes": obs.get("quakes") or [],
            "tsunami": obs.get("tsunami") or [],
            "gdacs": obs.get("gdacs") or [],
            "mosdac": obs.get("mosdac") or {},
            "moon": obs.get("moon") or {},
        },
        predictions={
            **dual,
            "hazards": build_hazard_forecast(
                f,
                flood_score=flood.score_pct,
                quakes=obs.get("quakes") or [],
                tsunami=obs.get("tsunami") or [],
                coast_km=f.get("coast_km"),
                cap_hit=cap_hit,
            ),
        },
        live=_build_live(loc, f, obs, flood.score_pct, generated_at),
        science=science,
        quality=_finalize_quality({
            "air": {
                "us_aqi": f.get("us_aqi"),
                "european_aqi": f.get("eu_aqi"),
                "pm2_5": f.get("om_pm25"),
                "pm10": f.get("om_pm10"),
                "co": f.get("om_co"),
                "co2": f.get("om_co2"),
                "no2": f.get("om_no2"),
                "so2": f.get("om_so2"),
                "o3": f.get("om_o3"),
                "nh3": air_nh3,
                "ch4": f.get("om_ch4"),
                "dust": f.get("om_dust"),
                "uv_index": f.get("om_uv"),
                "uv_index_clear_sky": f.get("om_uv_clear"),
                "pollen": pollen_pack,
                "cpcb": obs.get("naqi"),
                "waqi": obs.get("waqi"),
                "openweather": obs.get("ow_air"),
            },
            "climate": {
                "rh_now": f.get("rh_now"),
                "rh_max": f.get("rh_max"),
                "rh_min": f.get("rh_min"),
                "rh_mean": f.get("rh_mean"),
                "dew_point_c": f.get("dew_point_c"),
                "dew_max": f.get("dew_max"),
                "dew_min": f.get("dew_min"),
                "dew_mean": f.get("dew_mean"),
                "apparent_temp_c": f.get("apparent_temp_c"),
                "apparent_max": f.get("apparent_max"),
                "apparent_min": f.get("apparent_min"),
                "temp_now": f.get("temp_now"),
                "temp_max": (f.get("temp_max") or [None])[0] if f.get("temp_max") else None,
                "temp_min": (f.get("temp_min") or [None])[0] if f.get("temp_min") else None,
                "temp_mean": f.get("temp_mean"),
                "temp_80m": f.get("temp_80m"),
                "temp_120m": f.get("temp_120m"),
                "temp_180m": f.get("temp_180m"),
                "uv_index": f.get("om_uv"),
                "uv_index_clear_sky": f.get("om_uv_clear"),
                "uv_index_max": f.get("uv_index_max"),
                "uv_clear_max": f.get("uv_clear_max"),
                "precip_now": f.get("precip_now"),
                "precip_prob_now": f.get("precip_prob_now"),
                "precip_prob_max": (f.get("precip_prob") or [None])[0] if f.get("precip_prob") else None,
                "rain_now": f.get("rain_now"),
                "showers_now": f.get("showers_now"),
                "snowfall_now": f.get("snowfall_now"),
                "snow_depth_m": f.get("snow_depth_m"),
                "rain_sum": f.get("rain_sum"),
                "showers_sum": f.get("showers_sum"),
                "snowfall_sum": f.get("snowfall_sum"),
                "weather_code": f.get("weather_code"),
                "pressure_msl_hpa": f.get("pressure_msl_hpa"),
                "surface_pressure_hpa": f.get("surface_pressure_hpa"),
                "cloud_cover_pct": f.get("cloud_now"),
                "cloud_low": f.get("cloud_low"),
                "cloud_mid": f.get("cloud_mid"),
                "cloud_high": f.get("cloud_high"),
                "visibility_m": f.get("visibility_m"),
                "et_now": f.get("et_now"),
                "et0_today": f.get("et0_today"),
                "vpd_now": f.get("vpd_now"),
                "wind_10m": f.get("wind_now"),
                "wind_10m_max": f.get("wind_10m_max"),
                "wind_10m_mean": f.get("wind_10m_mean"),
                "wind_dir_10m": f.get("wind_dir_now"),
                "wind_gusts_10m": f.get("wind_gusts_now"),
                "wind_80m": f.get("wind_80m"),
                "wind_120m": f.get("wind_120m"),
                "wind_180m": f.get("wind_180m"),
                "wind_dir_80m": f.get("wind_dir_80m"),
                "wind_dir_120m": f.get("wind_dir_120m"),
                "wind_dir_180m": f.get("wind_dir_180m"),
                "soil_t_0": f.get("soil_t_0"),
                "soil_t_6": f.get("soil_t_6"),
                "soil_t_18": f.get("soil_t_18"),
                "soil_t_54": f.get("soil_t_54"),
                "soil_m_0_1": f.get("soil_m_0_1"),
                "soil_m_1_3": f.get("soil_m_1_3"),
                "soil_m_3_9": f.get("soil_m_3_9"),
                "soil_m_9_27": f.get("soil_m_9_27"),
                "soil_m_27_81": f.get("soil_m_27_81"),
                "soil_m3m3": f.get("soil_m3m3"),
                "sunrise": f.get("sunrise"),
                "sunset": f.get("sunset"),
                "daylight_s": f.get("daylight_s"),
                "sunshine_s": f.get("sunshine_s"),
                "shortwave_sum": f.get("shortwave_sum"),
            },
            "moon": obs.get("moon") or {},
            "marine": {
                "inland": f.get("marine_inland"),
                "wave_height_m": f.get("wave_height_m"),
                "wave_dir_deg": f.get("wave_dir_deg"),
                "wave_period_s": f.get("wave_period_s"),
                "wave_peak_period_s": f.get("wave_peak_period_s"),
                "wind_wave_height_m": f.get("wind_wave_height_m"),
                "wind_wave_dir_deg": f.get("wind_wave_dir_deg"),
                "wind_wave_period_s": f.get("wind_wave_period_s"),
                "wind_wave_peak_period_s": f.get("wind_wave_peak_period_s"),
                "swell_height_m": f.get("swell_height_m"),
                "swell_dir_deg": f.get("swell_dir_deg"),
                "swell_period_s": f.get("swell_period_s"),
                "swell_peak_period_s": f.get("swell_peak_period_s"),
                "swell2_height_m": f.get("swell2_height_m"),
                "swell2_dir_deg": f.get("swell2_dir_deg"),
                "swell2_period_s": f.get("swell2_period_s"),
                "swell3_height_m": f.get("swell3_height_m"),
                "swell3_dir_deg": f.get("swell3_dir_deg"),
                "swell3_period_s": f.get("swell3_period_s"),
                "sea_level_m": f.get("sea_level_m"),
                "sst_c": f.get("sst_c"),
                "ocean_current_ms": f.get("ocean_current_ms"),
                "ocean_current_dir": f.get("ocean_current_dir"),
            },
            "seismic": obs.get("quakes") or [],
            "tsunami": obs.get("tsunami") or [],
            "flood": {
                "discharge": (f.get("discharge") or [])[:7],
                "discharge_mean": (f.get("discharge_mean") or [])[:7],
                "trend": f.get("discharge_trend"),
                "source": "open-meteo-flood (GloFAS)",
            },
            "gdacs": obs.get("gdacs") or [],
            "mosdac": obs.get("mosdac") or {},
        }),
    )


def snapshot_tool_views(snap: DashboardSnapshot) -> dict[str, Any]:
    """Start-of-turn index for the Advisor. Locked nowcast only; no Kalman/gap."""
    from app.agents.views import snapshot_index

    return snapshot_index(snap)


def primary_reply(snap: DashboardSnapshot, locale: str, intent: str) -> tuple[str, str, dict]:
    actions = snap.prescriptive.actions
    pump = next((a for a in actions if a.template_id == "nowcast_pump_hold"), None)
    hold = next((a for a in actions if a.template_id == "irrigation_hold_rain"), None)
    apply = next((a for a in actions if a.template_id == "irrigation_apply"), None)
    flood = next((a for a in actions if a.template_id == "flood_prep"), None)
    if intent in {"irrigation", "rain"} and pump:
        text = render(pump.template_id or "", locale, pump.slots)
        return text, pump.template_id or "", pump.slots
    if intent in {"irrigation", "rain", "general"} and hold:
        text = render(hold.template_id or "", locale, hold.slots)
        return text, hold.template_id or "", hold.slots
    if intent == "irrigation" and apply:
        text = render(apply.template_id or "", locale, apply.slots)
        return text, apply.template_id or "", apply.slots
    if intent == "flood" and flood:
        text = render(flood.template_id or "", locale, flood.slots)
        return text, flood.template_id or "", flood.slots
    aqi_act = next((a for a in actions if a.template_id == "aqi_protect"), None)
    if intent == "aqi" and snap.descriptive.current.aqi is not None:
        slots = {
            "aqi": snap.descriptive.current.aqi,
            "category": snap.descriptive.current.aqi_category or "",
            "pollutant": snap.descriptive.current.aqi_pollutant or "",
        }
        if aqi_act:
            return render("aqi_protect", locale, aqi_act.slots), "aqi_protect", aqi_act.slots
        body = f"CPCB National AQI is {slots['aqi']} ({slots['category']}) at {snap.descriptive.current.aqi_station}."
        return render("generic_grounded", locale, {"body": body}), "generic_grounded", slots
    if intent == "price":
        mandi = (snap.ogd or {}).get("mandi") or []
        staples = ("rice", "paddy", "wheat", "potato", "onion", "jute", "mustard")
        def _rank(row: dict) -> tuple:
            name = (row.get("commodity") or "").lower()
            pref = next((i for i, s in enumerate(staples) if s in name), 99)
            return (pref, -(row.get("modal_price") or 0))
        ordered = sorted(mandi, key=_rank)
        bits = [
            f"{r.get('commodity')} {int(r.get('modal_price'))} INR/qtl ({r.get('market')})"
            for r in ordered[:5]
            if r.get("modal_price") is not None
        ]
        summary = "; ".join(bits) if bits else "no mandi arrivals reported for this district today"
        return render("mandi_summary", locale, {"summary": summary}), "mandi_summary", {"summary": summary}
    p = snap.predictive
    soil = snap.descriptive.current.soil_moisture_m3m3
    slots = {
        "rain_mm": p.precip_next_3d_mm,
        "prob": max(p.precip_probability_pct) if p.precip_probability_pct else 0,
        "tmax": ", ".join(f"{t}°C" for t in p.temp_max_c[:3]) or "n/a",
        "soil": f"{soil:.2f} m³/m³" if soil is not None else "n/a",
    }
    extra = ""
    if hold:
        extra = " " + render(hold.template_id or "", locale, hold.slots)
    if flood and intent != "irrigation":
        extra += " " + render(flood.template_id or "", locale, flood.slots)
    return render("forecast_summary", locale, slots) + extra, "forecast_summary", slots

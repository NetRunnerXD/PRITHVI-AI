from __future__ import annotations

from typing import Any

from app.ml.sky import compass, flow_compass, flow_deg, rose_bins, sky_label
from app.schemas.dashboard import LiveWatch
from app.schemas.location import Location

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


def _vera_pack(f: dict[str, Any], loc: Location, live_sat: dict[str, Any] | None) -> dict[str, Any]:
    from app.ml.vera import build_vera

    try:
        return build_vera(f, loc, live_sat, f.get("members") if isinstance(f.get("members"), dict) else {})
    except Exception as exc:
        return {
            "name": "VERA-MoE",
            "title": "Vision-Enhanced Regime-Adaptive Mixture-of-Experts",
            "error": str(exc),
            "guidance_only": True,
        }

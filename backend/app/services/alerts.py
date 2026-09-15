"""Assemble India-only live severe/warning alerts from official + model sources."""

from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from typing import Any

from app.data.india_mask import in_india
from app.providers import imd
from app.schemas.dashboard import EarlyWarning
from app.schemas.location import Location
from app.services.locality import alert_belongs, is_warning_or_worse, national_severe_belongs, port_relevant

SEVERE = {"extreme", "warning"}
IST = timezone(timedelta(hours=5, minutes=30))

_FOREIGN = (
    "philippines", "indonesia", "sumatra", "java", "myanmar", "vietnam",
    "malaysia", "thailand", "somalia", "madagascar",
)

KIND_HREF = {
    "flood": "map",
    "rainfall": "map",
    "cyclone": "map",
    "cloudburst": "nowcast",
    "extreme_rain": "nowcast",
    "thunderstorm": "nowcast",
    "lightning": "nowcast",
    "aqi": "risks",
    "tsunami": "map",
    "seismic": "map",
    "marine": "map",
    "heatwave": "predicted",
    "drought": "predicted",
    "wind": "predicted",
    "fog": "predicted",
    "uv": "predicted",
    "uv_heat": "predicted",
    "fire": "map",
    "landslide": "map",
}


def _parse_dt(raw: str | None) -> datetime | None:
    if not raw:
        return None
    s = str(raw).strip()
    try:
        return parsedate_to_datetime(s)
    except (TypeError, ValueError, IndexError):
        pass
    try:
        if s.endswith("Z"):
            s = s[:-1] + "+00:00"
        return datetime.fromisoformat(s)
    except ValueError:
        return None


def kind_from_text(title: str, body: str = "", hazard: str = "") -> str:
    t = f"{title} {body} {hazard}".lower()
    if "tsunami" in t:
        return "tsunami"
    if any(x in t for x in ("earthquake", "seismic", "quake")):
        return "seismic"
    if any(x in t for x in ("aqi", "air quality", "pm2.5", "pm10")):
        return "aqi"
    if "drought" in t or "dry spell" in t:
        return "drought"
    if any(x in t for x in ("heat wave", "heatwave", "heat risk")):
        return "heatwave"
    if any(x in t for x in ("fog", "visibility")):
        return "fog"
    if any(x in t for x in ("uv index", "ultraviolet", "uv radiation", "high-risk radiation")):
        return "uv"
    if any(x in t for x in ("landslide", "land slip", "mudslide", "debris flow")):
        return "landslide"
    if any(x in t for x in ("forest fire", "wildfire", "bushfire", "fire alert")):
        return "fire"
    if "cloudburst" in t:
        return "cloudburst"
    if any(x in t for x in ("cyclone", "depression", "landfall")):
        return "cyclone"
    if "flood" in t or "discharge" in t:
        return "flood"
    if "lightning" in t:
        return "lightning"
    if "thunder" in t or "squall" in t:
        return "thunderstorm"
    if "wave height" in t or "marine" in t or "port signal" in t:
        return "marine"
    if "wind" in t and "rain" not in t:
        return "wind"
    if "rain" in t:
        return "rainfall"
    return hazard or "weather"


def india_affects(item: dict[str, Any]) -> bool:
    blob = " ".join(
        str(item.get(k) or "")
        for k in ("title", "body", "place", "country", "name", "eventname")
    ).lower()
    lat, lon = item.get("lat"), item.get("lon")
    on_land = False
    if lat is not None and lon is not None:
        try:
            on_land = in_india(float(lat), float(lon))
        except (TypeError, ValueError):
            on_land = False
    mentions_india = any(
        x in blob
        for x in ("india", "bharat", "andaman", "nicobar", "lakshadweep", "bay of bengal", "arabian sea")
    )
    mentions_state = bool(imd.extract_region_hint(item.get("title") or "", item.get("body") or ""))
    foreign = any(f in blob for f in _FOREIGN)
    if foreign and not mentions_india and not on_land and not mentions_state:
        return False
    if on_land or mentions_india or mentions_state:
        return True
    if item.get("source") in {"imd-cap", "sachet-ndma", "IMD CAP"}:
        return True
    return False


def is_live(item: dict[str, Any], *, now: datetime | None = None, kind: str = "weather") -> bool:
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    exp = _parse_dt(item.get("expires_at") or item.get("expires"))
    if exp is not None:
        if exp.tzinfo is None:
            exp = exp.replace(tzinfo=IST)
        return exp >= now
    issued = _parse_dt(item.get("issued_at") or item.get("published") or item.get("time_iso"))
    if issued is None:
        return True
    if issued.tzinfo is None:
        issued = issued.replace(tzinfo=timezone.utc)
    hours = 72 if kind in {"cyclone", "tsunami"} else 48 if kind == "seismic" else 36
    mag = item.get("mag")
    try:
        if mag is not None and float(mag) >= 6:
            hours = 24 * 7
    except (TypeError, ValueError):
        pass
    return (now - issued) <= timedelta(hours=hours)


def _ew(
    *,
    id: str,
    severity: str,
    title: str,
    body: str = "",
    source: str,
    hazard: str,
    kind: str | None = None,
    scope: str | None = None,
    issued_at: str | None = None,
    url: str | None = None,
    href_kind: str | None = None,
    states: list[str] | None = None,
    distance_km: float | None = None,
    lat: float | None = None,
    lon: float | None = None,
    expires_at: str | None = None,
    linked_risk_id: str | None = None,
    eta_min: float | None = None,
    window_start: str | None = None,
    window_end: str | None = None,
) -> EarlyWarning:
    kind = kind or kind_from_text(title, body, hazard)
    href = href_kind or ("bulletin" if url else KIND_HREF.get(kind, "risks"))
    hint = imd.extract_region_hint(title, body)
    st = list(states or [])
    if hint and hint not in st:
        st.append(hint)
    return EarlyWarning(
        id=id[:64],
        severity=severity,
        title=title[:200],
        body=(body or "")[:400],
        lenses=["predictive"],
        source=source,
        hazard=hazard,
        kind=kind,
        scope=scope,
        issued_at=issued_at,
        url=url,
        href_kind=href,
        states=st,
        distance_km=distance_km,
        lat=lat,
        lon=lon,
        expires_at=expires_at or window_end,
        linked_risk_id=linked_risk_id,
        eta_min=eta_min,
        window_start=window_start,
        window_end=window_end,
    )


def _ledger_pin_warnings(loc: Location) -> list[EarlyWarning]:
    """Gated live/predicted events near the pin from the sat Mongo ledger.

    Risks stay snapshot-computed. Official CAP still wins on kind+state.
    """
    try:
        from app.store.hazard_events import query
    except Exception:
        return []
    lat, lon = float(loc.lat or 0), float(loc.lon or 0)
    if not lat or not lon:
        return []
    out: list[EarlyWarning] = []
    try:
        rows = query(past_h=12)
    except Exception:
        return []
    for row in rows:
        if row.get("phase") not in {"live", "predicted"}:
            continue
        gate = row.get("gate") or {}
        if not gate.get("ok") and row.get("engine") != "open-meteo-thunder":
            continue
        try:
            rlat, rlon = float(row["lat"]), float(row["lon"])
        except (KeyError, TypeError, ValueError):
            continue
        dkm = ((rlat - lat) ** 2 + (rlon - lon) ** 2) ** 0.5 * 111.3
        kind = str(row.get("kind") or "thunderstorm")
        title = str(row.get("title") or f"{kind.replace('_', ' ').capitalize()} — {row.get('place') or 'Local'}")
        if dkm <= 80:
            out.append(
                _ew(
                    id=f"ledger-{row.get('event_id')}",
                    severity="warning",
                    title=title[:200],
                    body=(row.get("verify") or {}).get("note") or row.get("note") or "Sat ledger event.",
                    source="prithvi-ai-ledger",
                    hazard="weather",
                    kind=kind if kind != "cloud" else "thunderstorm",
                    scope="local",
                    lat=rlat,
                    lon=rlon,
                    distance_km=round(dkm, 1),
                    window_start=row.get("started_at"),
                    window_end=row.get("closes_at"),
                    href_kind="map",
                )
            )
        elif gate.get("ok") and row.get("p_cloudburst", 0) and float(row.get("p_cloudburst") or 0) >= 0.4:
            out.append(
                _ew(
                    id=f"ledger-nat-{row.get('event_id')}",
                    severity="warning",
                    title=f"Severe Convective Storm — {row.get('place') or 'India'}",
                    body=(row.get("verify") or {}).get("note") or row.get("note") or "Deep convective system detected by satellite.",
                    source="prithvi-ai-ledger",
                    hazard="weather",
                    kind=kind if kind != "cloud" else "thunderstorm",
                    scope="india",
                    lat=rlat,
                    lon=rlon,
                    distance_km=round(dkm, 1),
                    window_start=row.get("started_at"),
                    window_end=row.get("closes_at"),
                    href_kind="map",
                )
            )
    return out


def _norm_key(w: EarlyWarning) -> str:
    return re.sub(r"[^a-z0-9]", "", f"{w.kind or w.hazard}{(w.states or [''])[:1]}{w.title}".lower())[:96]


def assemble_warnings(
    loc: Location,
    caps: list[dict],
    flood_score: int,
    f: dict,
    quakes: list[dict],
    tsunami: list[dict],
    naqi: dict | None,
    *,
    gdacs_rows: list[dict] | None = None,
    sachet_rows: list[dict] | None = None,
    port: dict | None = None,
    risks: list[Any] | None = None,
    vera: dict | None = None,
    nowcast: dict | None = None,
    convective: dict | None = None,
    scan_hits: list[dict] | None = None,
    fires: list[dict] | None = None,
) -> list[EarlyWarning]:
    out: list[EarlyWarning] = []
    seen: set[str] = set()
    official_keys: set[str] = set()

    def add(w: EarlyWarning, official: bool = False) -> None:
        if w.severity not in SEVERE:
            return
        if w.scope != "local" and not india_affects(
            {"title": w.title, "body": w.body, "lat": w.lat, "lon": w.lon, "source": w.source}
        ):
            if w.source not in {
                "prithvi-ai-risk",
                "vera-extremes",
                "nowcast",
                "prithvi-netra",
                "open-meteo-flood",
                "open-meteo-flood + local-ml-v2",
                "data.gov.in / CPCB",
                "imd-port",
            }:
                return
        k = _norm_key(w)
        pair = f"{w.kind}|{(w.states[0] if w.states else loc.state or '').lower()}"
        if official:
            official_keys.add(pair)
        elif pair in official_keys:
            return
        if k in seen:
            return
        seen.add(k)
        out.append(w)

    local = imd.alerts_for_location(caps, loc)
    local_ids = {str(a.get("id")) for a in local}
    for a in local:
        if not is_live(a, kind="rainfall"):
            continue
        raw = a.get("title") or "IMD alert"
        title = imd.humanize_cap_title(raw, a.get("body") or "", loc.place_name or loc.district)
        sev = imd.severity_from_title(raw + " " + title)
        if sev not in SEVERE and sev != "alert":
            continue
        if sev == "alert":
            sev = "warning" if imd.is_national_severe(raw, a.get("body") or "") else sev
        if sev not in SEVERE:
            continue
        add(
            _ew(
                id=str(a.get("id"))[:64],
                severity=sev if sev in SEVERE else "warning",
                title=title,
                body=imd.clean_cap_body(a.get("body") or "", title=title, raw_title=raw),
                source="imd-cap",
                hazard="weather",
                scope="local",
                issued_at=a.get("published"),
                url=a.get("link") or a.get("url"),
                linked_risk_id="flood" if "rain" in title.lower() else None,
            ),
            official=True,
        )
    for a in imd.national_severe(caps):
        if str(a.get("id")) in local_ids:
            continue
        if not is_live(a, kind=kind_from_text(a.get("title") or "", a.get("body") or "")):
            continue
        raw = a.get("title") or "IMD alert"
        loc_hint = imd.extract_region_hint(raw, a.get("body") or "")
        tag = f"{loc_hint} (India)" if loc_hint else "India"
        title = imd.humanize_cap_title(raw, a.get("body") or "", tag)
        sev = imd.severity_from_title(raw + " " + title)
        if sev not in SEVERE and sev != "alert":
            continue
        if sev == "alert":
            sev = "warning"
        add(
            _ew(
                id=f"in_{str(a.get('id'))[:56]}",
                severity=sev,
                title=title,
                body=imd.clean_cap_body(a.get("body") or "", title=title, raw_title=raw),
                source="imd-cap",
                hazard="weather",
                scope="india",
                issued_at=a.get("published"),
                url=a.get("link") or a.get("url"),
                states=[loc_hint] if loc_hint else [],
            ),
            official=True,
        )

    for item in sachet_rows or []:
        raw = item.get("title") or "SACHET alert"
        body = item.get("body") or ""
        local_ok = alert_belongs(item, loc)
        sev = imd.severity_from_title(raw + " " + body)
        hint = imd.extract_region_hint(raw, body)
        if not local_ok and not is_warning_or_worse(item) and not hint:
            continue
        if not is_live(item, kind=kind_from_text(raw, body)):
            continue
        if sev not in SEVERE and (hint or is_warning_or_worse(item)):
            sev = "warning"
        if sev not in SEVERE:
            continue
        add(
            _ew(
                id=str(item.get("id") or raw)[:64],
                severity=sev,
                title=imd.humanize_cap_title(raw, body, hint or (loc.district if local_ok else "India")),
                body=imd.clean_cap_body(body, title=raw, raw_title=raw) or "NDMA SACHET.",
                source="sachet-ndma",
                hazard="weather",
                scope="local" if local_ok else "india",
                issued_at=item.get("published"),
                url=item.get("link") or item.get("url"),
                states=[hint] if hint else [],
            ),
            official=True,
        )

    for g in gdacs_rows or []:
        if not india_affects(g):
            continue
        et = str(g.get("event_type") or "").upper()
        lvl = str(g.get("alert_level") or "").lower()
        if et not in {"TC", "TS", "EQ", "FL", "DR", "WF"}:
            continue
        if lvl in {"green"}:
            continue
        if et == "EQ" and lvl not in {"orange", "red"}:
            continue
        if lvl not in {"orange", "red"} and et not in {"TC", "TS"}:
            continue
        haz = {"TC": "weather", "TS": "tsunami", "EQ": "seismic", "FL": "flood", "DR": "drought", "WF": "weather"}.get(et, "weather")
        add(
            _ew(
                id=f"gdacs_{g.get('id')}",
                severity="warning",
                title=str(g.get("title") or f"GDACS {et}")[:160],
                body=str(g.get("body") or g.get("alert_level") or "")[:280],
                source="gdacs",
                hazard=haz,
                kind={"TC": "cyclone", "TS": "tsunami", "EQ": "seismic", "FL": "flood", "DR": "drought", "WF": "fire"}.get(et),
                scope="india",
                url=g.get("url"),
                lat=g.get("lat"),
                lon=g.get("lon"),
            ),
            official=True,
        )

    for q in quakes or []:
        mag = float(q.get("mag") or 0)
        dist = q.get("distance_km")
        near = dist is not None and float(dist) <= 150
        if not india_affects({**q, "title": q.get("place") or "", "body": ""}) and not near:
            continue
        if not is_live({**q, "issued_at": q.get("time_iso")}, kind="seismic"):
            continue
        inside = False
        try:
            if q.get("lat") is not None and q.get("lon") is not None:
                inside = in_india(float(q["lat"]), float(q["lon"]))
        except (TypeError, ValueError):
            inside = False
        if mag >= 6.0 or (mag >= 4.5 and (near or inside)):
            add(
                _ew(
                    id=str(q.get("id") or f"usgs_{mag}"),
                    severity="warning" if mag >= 6 else "warning",
                    title=(
                        f"M{mag:.1f} earthquake {int(dist)} km from {loc.district}"
                        if near and dist is not None
                        else f"M{mag:.1f} earthquake — {q.get('place') or 'India'}"
                    ),
                    body=q.get("place") or "USGS FDSN event in India.",
                    source="usgs-fdsn",
                    hazard="seismic",
                    scope="local" if near else "india",
                    issued_at=q.get("time_iso"),
                    distance_km=float(dist) if dist is not None else None,
                    lat=q.get("lat"),
                    lon=q.get("lon"),
                    url=f"https://earthquake.usgs.gov/earthquakes/eventpage/{q.get('id')}" if q.get("id") else None,
                ),
                official=True,
            )

    for i, item in enumerate((tsunami or [])[:6]):
        title = item.get("title") or "INCOIS ITEWS bulletin"
        low = title.lower() + " " + (item.get("body") or "").lower()
        if any(x in low for x in ("no threat", "no tsunami", "does not exist", "all clear", "nil")) and not item.get("threat"):
            continue
        if not (item.get("threat") or any(x in low for x in ("warning", "alert", "threat exists"))):
            continue
        if not india_affects(item) and "india" not in low and "andaman" not in low:
            continue
        add(
            _ew(
                id=f"incois_{i}",
                severity="warning",
                title=title[:160],
                body=(item.get("body") or "")[:280],
                source="incois-itews",
                hazard="tsunami",
                scope="india",
                url=item.get("url") or item.get("detail") or item.get("link"),
            ),
            official=True,
        )

    naqi_val = (naqi or {}).get("value")
    if naqi_val is not None and int(naqi_val) >= 301:
        add(
            _ew(
                id="cpcb_aqi",
                severity="warning" if int(naqi_val) >= 301 else "warning",
                title=f"CPCB National AQI {int(naqi_val)} — {(naqi or {}).get('category') or 'unhealthy'}",
                body=f"Station {(naqi or {}).get('station') or loc.district}. Dominant {(naqi or {}).get('dominant_pollutant') or 'n/a'}.",
                source="data.gov.in / CPCB",
                hazard="air",
                kind="aqi",
                scope="local",
                linked_risk_id="air_quality",
            )
        )

    wave = f.get("wave_height_m")
    if wave is not None and float(wave) >= 3.0:
        add(
            _ew(
                id="om_marine_wave",
                severity="warning",
                title=f"Significant wave height {float(wave):.1f} m",
                body="Open-Meteo marine forecast. Check INCOIS sea-state bulletins.",
                source="open-meteo-marine",
                hazard="marine",
                scope="local",
            )
        )

    if flood_score >= 70:
        add(
            _ew(
                id="model_flood",
                severity="warning",
                title="Modelled flood risk is high for this district",
                body="Weighted risk from rainfall anomaly, GloFAS discharge and soil saturation.",
                source="open-meteo-flood + local-ml-v2",
                hazard="flood",
                kind="flood",
                scope="local",
                linked_risk_id="flood",
                href_kind="risks",
            )
        )
    elif f.get("discharge_trend") == "rising" and flood_score >= 55:
        add(
            _ew(
                id="om_discharge_rise",
                severity="warning",
                title="River discharge is rising",
                body=f"Open-Meteo GloFAS trend is rising. Model flood score {flood_score}%.",
                source="open-meteo-flood",
                hazard="flood",
                kind="flood",
                scope="local",
                linked_risk_id="flood",
                href_kind="map",
            )
        )

    risk_map = {getattr(r, "id", None): r for r in (risks or [])}
    drought = risk_map.get("drought")
    if drought is not None and int(getattr(drought, "score_pct", 0) or 0) >= 75:
        add(
            _ew(
                id="model_drought",
                severity="warning",
                title=f"Drought risk {int(drought.score_pct)}% at {loc.district}",
                body="Rainfall deficit and dry soil on this pin.",
                source="prithvi-ai-risk",
                hazard="drought",
                kind="drought",
                scope="local",
                linked_risk_id="drought",
                href_kind="risks",
            )
        )
    heat = risk_map.get("heat")
    if heat is not None and int(getattr(heat, "score_pct", 0) or 0) >= 70:
        add(
            _ew(
                id="model_heat",
                severity="warning",
                title=f"Heat risk {int(heat.score_pct)}% at {loc.district}",
                body="High afternoon temperature and humidity on this pin.",
                source="prithvi-ai-risk",
                hazard="weather",
                kind="heatwave",
                scope="local",
                linked_risk_id="heat",
                href_kind="predicted",
            )
        )

    ext = (vera or {}).get("extremes") or vera or {}
    if isinstance(ext, dict):
        heat_x = ext.get("heat") or ext.get("heat_wave") or {}
        rain_x = ext.get("rain") or ext.get("precip") or ext.get("heavy_rain") or {}
        wind_x = ext.get("wind") or ext.get("high_wind") or {}
        if (heat_x.get("level_key") or heat_x.get("level") or "") in {"watch", "Warning"} or heat_x.get("level") == "Warning":
            add(
                _ew(
                    id="vera_heat",
                    severity="warning",
                    title=f"Predicted heatwave — {loc.district}",
                    body="Ensemble extremes: consecutive hot days.",
                    source="vera-extremes",
                    hazard="weather",
                    kind="heatwave",
                    scope="local",
                    href_kind="predicted",
                )
            )
        if (rain_x.get("level_key") or "") == "watch" or rain_x.get("level") == "Warning":
            add(
                _ew(
                    id="vera_rain",
                    severity="warning",
                    title=f"Predicted heavy rainfall — {loc.district}",
                    body="Ensemble extremes: IMD-style heavy rain probability.",
                    source="vera-extremes",
                    hazard="weather",
                    kind="rainfall",
                    scope="local",
                    href_kind="predicted",
                )
            )
        if (wind_x.get("level_key") or "") == "watch" or wind_x.get("level") == "Warning":
            add(
                _ew(
                    id="vera_wind",
                    severity="warning",
                    title=f"Predicted high wind — {loc.district}",
                    body="Ensemble wind peak at warning threshold.",
                    source="vera-extremes",
                    hazard="weather",
                    kind="wind",
                    scope="local",
                    href_kind="predicted",
                )
            )

    conv = convective or {}
    lightning_p = conv.get("lightning") if isinstance(conv.get("lightning"), dict) else {}
    burst_p = conv.get("cloudburst") if isinstance(conv.get("cloudburst"), dict) else conv
    down_p = conv.get("downburst") if isinstance(conv.get("downburst"), dict) else {}

    def _pack_score(p: dict) -> tuple[int, str]:
        if not isinstance(p, dict) or not p:
            return 0, "quiet"
        sc = int(p.get("score_pct") or p.get("cloudburst_score") or p.get("score") or 0)
        lv = str(p.get("level") or "")
        if not lv:
            lv = "alert" if sc >= 70 else "watch" if sc >= 45 else "quiet"
        return sc, lv

    burst = burst_p if isinstance(burst_p, dict) else {}
    cb_sc, cb_lv = _pack_score(burst)
    cb_eta = burst.get("eta_min")
    cb_label = str(burst.get("label") or "")
    qualifies = bool(burst.get("qualifies"))
    if not cb_label:
        if qualifies or (cb_sc >= 70 and cb_lv in {"watch", "alert"}):
            cb_label = "cloudburst_conditions"
        elif cb_lv in {"watch", "alert"} or cb_sc >= 45:
            cb_label = "extreme_rain"
    if qualifies or cb_label == "cloudburst_conditions":
        add(
            _ew(
                id="conv_burst",
                severity="warning",
                title=f"Cloudburst conditions — {loc.district}",
                body="IR stall + deep top or orographic lift. Watch only; not a confirmed 100 mm/h IMD cloudburst.",
                source="nowcast",
                hazard="weather",
                kind="cloudburst",
                scope="local",
                href_kind="nowcast",
                eta_min=cb_eta,
                window_start=burst.get("window_start"),
                window_end=burst.get("window_end"),
            )
        )
    elif cb_label == "extreme_rain" or (cb_sc >= 45 and cb_lv in {"watch", "alert"}):
        add(
            _ew(
                id="conv_extreme_rain",
                severity="warning",
                title=f"Extreme rain nowcast — {loc.district}",
                body=f"Deep convection / heavy-rain proxy (score {cb_sc}%). Not labelled cloudburst.",
                source="nowcast",
                hazard="weather",
                kind="extreme_rain",
                scope="local",
                href_kind="nowcast",
                eta_min=cb_eta,
                window_start=burst.get("window_start"),
                window_end=burst.get("window_end"),
            )
        )

    lg_sc, lg_lv = _pack_score(lightning_p)
    n_stroke = int(lightning_p.get("n_strokes") or conv.get("n_strokes") or f.get("lightning") or 0)
    gate = lightning_p.get("gate") if isinstance(lightning_p.get("gate"), dict) else {}
    gate_ok = bool(gate.get("ok")) if gate else n_stroke >= 1
    lg_win_s = lightning_p.get("window_start") or (conv.get("window") or {}).get("window_start")
    lg_win_e = lightning_p.get("window_end") or (conv.get("window") or {}).get("window_end")
    if n_stroke >= 1 or (gate_ok and (lg_lv in {"watch", "alert"} or lg_sc >= 45)):
        near = lightning_p.get("nearest_km")
        near_s = f" Nearest stroke {near} km." if near is not None else ""
        lg_eta = None
        if isinstance(lightning_p.get("nowcast"), dict):
            lg_eta = lightning_p["nowcast"].get("eta_min")
        lg_eta = lg_eta if lg_eta is not None else lightning_p.get("eta_min")
        add(
            _ew(
                id="conv_lightning",
                severity="warning",
                title=f"Lightning nowcast — {loc.district}",
                body=f"{n_stroke} stroke(s) scored {lg_sc}%.{near_s}",
                source="nowcast",
                hazard="weather",
                kind="lightning",
                scope="local",
                href_kind="nowcast",
                eta_min=lg_eta,
                window_start=lg_win_s,
                window_end=lg_win_e,
            )
        )

    db_sc, db_lv = _pack_score(down_p)
    codes: list[int] = []
    for raw_c in (f.get("hourly_weather_code") or [])[:6]:
        try:
            codes.append(int(raw_c))
        except (TypeError, ValueError):
            pass
    try:
        if f.get("weather_code") is not None:
            codes.append(int(f.get("weather_code")))
    except (TypeError, ValueError):
        pass
    thunder_code = any(c >= 95 for c in codes)
    nc = nowcast or {}
    take_cover = any(a.get("verb") == "take_cover" for a in (nc.get("actions") or []))
    if take_cover or thunder_code or db_lv in {"watch", "alert"} or db_sc >= 45:
        db_eta = down_p.get("eta_min") if isinstance(down_p, dict) else None
        add(
            _ew(
                id="nowcast_cover",
                severity="warning",
                title=f"Thunderstorm nowcast — {loc.district}",
                body=(
                    "0–6 h take-cover action."
                    if take_cover
                    else f"WMO thunder code or downburst score {db_sc}%."
                ),
                source="nowcast",
                hazard="weather",
                kind="thunderstorm",
                scope="local",
                href_kind="nowcast",
                eta_min=0 if thunder_code else db_eta,
                window_start=down_p.get("window_start") if isinstance(down_p, dict) else None,
                window_end=down_p.get("window_end") if isinstance(down_p, dict) else None,
            )
        )

    try:
        from app.science.env_hazards import build as build_env

        env = build_env(f, loc=loc, convective=conv, bands=f.get("insat_channels") if isinstance(f, dict) else None)
    except Exception:
        env = {}
    fog = env.get("fog") if isinstance(env, dict) else None
    if isinstance(fog, dict) and fog.get("alert"):
        vis = fog.get("vis_m")
        vis_s = f" Visibility {int(vis)} m." if vis is not None else ""
        add(
            _ew(
                id="env_fog",
                severity="warning",
                title=f"{str(fog.get('grade') or 'dense').replace('_', ' ').title()} fog — {loc.district}",
                body=f"Expected {fog.get('window_start') or '?'} to {fog.get('window_end') or '?'}.{vis_s} Slow travel.",
                source="env-hazards",
                hazard="weather",
                kind="fog",
                scope="local",
                href_kind="predicted",
                window_start=fog.get("window_start"),
                window_end=fog.get("window_end"),
            )
        )
    heat_e = env.get("heatwave") if isinstance(env, dict) else None
    if isinstance(heat_e, dict) and (heat_e.get("alert") or heat_e.get("window_start")):
        existing_heat = next((w for w in out if w.kind == "heatwave"), None)
        if existing_heat is not None:
            if not existing_heat.window_start:
                existing_heat.window_start = heat_e.get("window_start")
            if not existing_heat.window_end:
                existing_heat.window_end = heat_e.get("window_end")
                existing_heat.expires_at = existing_heat.expires_at or heat_e.get("window_end")
        elif heat_e.get("alert"):
            kind_h = "severe heatwave" if heat_e.get("imd_severe") else "heatwave"
            if heat_e.get("humid_heat") and not heat_e.get("imd_qualifies"):
                kind_h = "humid heat"
            add(
                _ew(
                    id="env_heat",
                    severity="warning",
                    title=f"{kind_h.title()} — {loc.district}",
                    body=(
                        f"IMD {heat_e.get('zone')} threshold {heat_e.get('threshold_c')} °C"
                        + (f", Tmax {heat_e.get('tmax_c')} °C" if heat_e.get("tmax_c") is not None else "")
                        + (f", WBGT {heat_e.get('wbgt_peak_c')} °C" if heat_e.get("wbgt_peak_c") is not None else "")
                        + f". Expected {heat_e.get('window_start') or '?'} to {heat_e.get('window_end') or '?'}."
                    ),
                    source="env-hazards",
                    hazard="weather",
                    kind="heatwave",
                    scope="local",
                    href_kind="predicted",
                    linked_risk_id="heat",
                    window_start=heat_e.get("window_start"),
                    window_end=heat_e.get("window_end"),
                )
            )
    uv = env.get("uv") if isinstance(env, dict) else None
    if isinstance(uv, dict) and uv.get("alert"):
        add(
            _ew(
                id="env_uv",
                severity="warning",
                title=f"Very high UV (index {uv.get('uv_peak')}) — {loc.district}",
                body=f"WHO {uv.get('who_category', 'very_high').replace('_', ' ')}. Expected {uv.get('window_start') or '?'} to {uv.get('window_end') or '?'}. Shade and sleeves.",
                source="env-hazards",
                hazard="weather",
                kind="uv",
                scope="local",
                href_kind="predicted",
                window_start=uv.get("window_start"),
                window_end=uv.get("window_end"),
            )
        )
    slide = env.get("landslide") if isinstance(env, dict) else None
    if isinstance(slide, dict) and slide.get("alert"):
        add(
            _ew(
                id="env_landslide",
                severity="warning",
                title=f"Landslide watch — {loc.district}",
                body=(
                    f"Orographic rain {slide.get('rain_3d_mm')} mm / 3 days"
                    f". Expected {slide.get('window_start') or '?'} to {slide.get('window_end') or '?'}."
                    " Stay off steep cuts."
                ),
                source="env-hazards",
                hazard="weather",
                kind="landslide",
                scope="local",
                href_kind="map",
                lat=loc.lat,
                lon=loc.lon,
                window_start=slide.get("window_start"),
                window_end=slide.get("window_end"),
            )
        )

    nearby_fires = []
    for fr in fires or []:
        try:
            d = ((float(fr["lat"]) - loc.lat) ** 2 + (float(fr["lon"]) - loc.lon) ** 2) ** 0.5 * 111.3
        except (TypeError, ValueError, KeyError):
            continue
        if d <= 40:
            nearby_fires.append({**fr, "distance_km": round(d, 1)})
        elif int(fr.get("n") or 0) >= 8 or float(fr.get("frp_mw") or 0) >= 40:
            add(
                _ew(
                    id=str(fr.get("id") or f"fire_{fr.get('lat')}")[:64],
                    severity="warning",
                    title=f"Forest fire hotspot — {fr.get('place') or 'India'}",
                    body=f"{int(fr.get('n') or 0)} VIIRS detections, FRP {fr.get('frp_mw')} MW. NASA FIRMS thermal, not a burned-area map.",
                    source="nasa-firms",
                    hazard="weather",
                    kind="fire",
                    scope="india",
                    href_kind="map",
                    lat=fr.get("lat"),
                    lon=fr.get("lon"),
                    states=[fr["state"]] if fr.get("state") else [],
                )
            )
    if nearby_fires:
        top = nearby_fires[0]
        add(
            _ew(
                id="firms_pin",
                severity="warning",
                title=f"Forest fire near {loc.district}",
                body=f"{int(top.get('n') or 0)} VIIRS hotspot(s) {top.get('distance_km')} km away, FRP {top.get('frp_mw')} MW. Avoid smoke and open burns.",
                source="nasa-firms",
                hazard="weather",
                kind="fire",
                scope="local",
                href_kind="map",
                lat=top.get("lat"),
                lon=top.get("lon"),
            )
        )

    compound = env.get("compound") if isinstance(env, dict) else None
    if isinstance(compound, dict) and compound.get("alert"):
        add(
            _ew(
                id="env_uv_heat",
                severity="warning",
                title=f"High UV and heat together — {loc.district}",
                body=f"UVI {compound.get('uv_peak')} with WBGT {compound.get('wbgt_peak_c')} °C. Limit midday outdoor work.",
                source="env-hazards",
                hazard="weather",
                kind="uv_heat",
                scope="local",
                href_kind="predicted",
                window_start=compound.get("window_start"),
                window_end=compound.get("window_end"),
            )
        )

    port = port or {}
    if port.get("active") and port_relevant(loc):
        add(
            _ew(
                id="imd_port_hooghly",
                severity="warning",
                title=f"Hooghly port signal {port.get('signal') or ''}".strip(),
                body="IMD coastal bulletin for Kolkata & Haldia.",
                source="imd-port",
                hazard="marine",
                scope="local",
                url=port.get("url"),
            ),
            official=True,
        )

    for w in _ledger_pin_warnings(loc):
        add(w)

    for hit in scan_hits or []:
        st = str(hit.get("state") or "")
        kind = str(hit.get("kind") or "flood")
        if st.lower() == (loc.state or "").lower() and kind in {w.kind for w in out if w.scope == "local"}:
            continue
        add(
            _ew(
                id=f"scan_{kind}_{st}"[:64],
                severity="warning",
                title=str(hit.get("title") or f"Predicted {kind} warning — {st}"),
                body=str(hit.get("body") or "Cached capital scan."),
                source="prithvi-netra",
                hazard="flood" if kind == "flood" else "weather",
                kind=kind,
                scope="india",
                states=[st] if st else [],
                lat=hit.get("lat"),
                lon=hit.get("lon"),
                href_kind="map" if kind in {"flood", "rainfall", "cyclone"} else "predicted",
            )
        )

    order = {"extreme": 0, "warning": 1, "alert": 2}
    out.sort(key=lambda w: (order.get(w.severity, 9), w.issued_at or ""), reverse=False)
    return out

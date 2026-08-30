"""Deterministic 7-day outlook and plot-scale water balance. LLM never computes this."""

from __future__ import annotations

from typing import Any

from app.science.hysteresis import initial_state, step_day


def build_outlook(f: dict[str, Any]) -> dict[str, Any]:
    precip = list(f.get("precip_days") or [])
    probs = list(f.get("precip_prob") or [])
    tmax = list(f.get("temp_max") or [])
    tmin = list(f.get("temp_min") or [])
    et0 = list(f.get("et0_days") or [])
    times = list(f.get("daily_times") or [])
    n = max(len(precip), len(times), 0)
    n = min(7, n)
    st = initial_state(f)
    days: list[dict[str, Any]] = []
    irrigate_on: list[str] = []
    flood_days: list[str] = []
    for i in range(n):
        p = float(precip[i]) if i < len(precip) else 0.0
        e = float(et0[i]) if i < len(et0) else 3.0
        pr = int(probs[i]) if i < len(probs) else 0
        tx = float(tmax[i]) if i < len(tmax) else None
        tn = float(tmin[i]) if i < len(tmin) else None
        date = str(times[i]) if i < len(times) else f"d+{i}"
        st = step_day(st, p, e)
        soil = st["soil"]
        irrigate = p < 4.0 and soil < 0.26 and pr < 55
        flood_watch = p >= 25.0 or st["runoff_mm"] >= 12.0
        if irrigate:
            irrigate_on.append(date)
        if flood_watch:
            flood_days.append(date)
        days.append(
            {
                "date": date,
                "precip_mm": round(p, 1),
                "precip_prob_pct": pr,
                "temp_max_c": round(tx, 1) if tx is not None else None,
                "temp_min_c": round(tn, 1) if tn is not None else None,
                "et0_mm": round(e, 2),
                "soil_m3m3": round(soil, 3),
                "water_balance_mm": round(p - e, 2),
                "runoff_mm": st["runoff_mm"],
                "limb": st["limb"],
                "irrigate": irrigate,
                "flood_watch": flood_watch,
            }
        )
    p7 = sum(float(x) for x in precip[:7])
    e7 = sum(float(x) for x in et0[:7])
    return {
        "days": days,
        "precip_7d_mm": round(p7, 1),
        "et0_7d_mm": round(e7, 2),
        "water_balance_7d_mm": round(p7 - e7, 1),
        "irrigate_dates": irrigate_on,
        "flood_watch_dates": flood_days,
        "method": "open-meteo daily + hysteresis soil v1",
    }


def _f_at(seq: list, i: int):
    if i < 0 or i >= len(seq):
        return None
    v = seq[i]
    if v is None:
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def build_hourly_7d(f: dict[str, Any]) -> list[dict[str, Any]]:
    """Next 7 IST calendar days, hour by hour, from Open-Meteo hourly arrays."""
    from datetime import date, timedelta

    from app.ml.features import _today_ist
    from app.ml.sky import sky_label

    times = list(f.get("hourly_times") or [])
    if not times:
        return []
    today = date.fromisoformat(_today_ist())
    last = today + timedelta(days=6)
    precip = list(f.get("hourly_precip") or [])
    prob = list(f.get("hourly_prob") or [])
    temp = list(f.get("hourly_temp") or [])
    wind = list(f.get("hourly_wind") or [])
    gust = list(f.get("hourly_gust") or [])
    wdir = list(f.get("hourly_wind_dir") or [])
    rh = list(f.get("hourly_rh") or [])
    cloud = list(f.get("hourly_cloud") or [])
    code = list(f.get("hourly_weather_code") or [])
    vis = list(f.get("hourly_vis") or [])
    out: list[dict[str, Any]] = []
    for i, raw in enumerate(times):
        ts = str(raw)
        day = ts[:10]
        if len(day) < 10 or day[4:5] != "-":
            continue
        try:
            d = date.fromisoformat(day)
        except ValueError:
            continue
        if d < today or d > last:
            continue
        hour = ts[11:16] if len(ts) >= 16 else ts
        wc = _f_at(code, i)
        sky, kind = sky_label(int(wc) if wc is not None else None)
        vis_m = _f_at(vis, i)
        out.append(
            {
                "t": ts,
                "date": day,
                "hour": hour,
                "precip_mm": None if _f_at(precip, i) is None else round(_f_at(precip, i), 2),
                "precip_prob_pct": None if _f_at(prob, i) is None else int(_f_at(prob, i)),
                "temp_c": None if _f_at(temp, i) is None else round(_f_at(temp, i), 1),
                "wind_kmh": None if _f_at(wind, i) is None else round(_f_at(wind, i), 1),
                "wind_gust_kmh": None if _f_at(gust, i) is None else round(_f_at(gust, i), 1),
                "wind_dir_deg": None if _f_at(wdir, i) is None else round(_f_at(wdir, i), 0),
                "rh_pct": None if _f_at(rh, i) is None else round(_f_at(rh, i), 0),
                "cloud_pct": None if _f_at(cloud, i) is None else round(_f_at(cloud, i), 0),
                "weather_code": None if wc is None else int(wc),
                "sky_label": sky,
                "sky_kind": kind,
                "visibility_km": None if vis_m is None else round(vis_m / 1000.0, 1),
            }
        )
    return out


def compact_compare(a: dict[str, Any], b: dict[str, Any]) -> dict[str, Any]:
    """a/b are snapshot.model_dump() fragments."""
    pa, pb = a.get("predictive") or {}, b.get("predictive") or {}
    ra = {r["id"]: r["score_pct"] for r in (a.get("risks") or [])}
    rb = {r["id"]: r["score_pct"] for r in (b.get("risks") or [])}
    ca, cb = (a.get("descriptive") or {}).get("current") or {}, (b.get("descriptive") or {}).get("current") or {}

    def sub(x, y):
        if x is None or y is None:
            return None
        try:
            return round(float(x) - float(y), 2)
        except (TypeError, ValueError):
            return None

    return {
        "rain_3d_mm": sub(pa.get("precip_next_3d_mm"), pb.get("precip_next_3d_mm")),
        "water_balance_7d_mm": sub(pa.get("water_balance_7d_mm"), pb.get("water_balance_7d_mm")),
        "flood_score": sub(ra.get("flood"), rb.get("flood")),
        "drought_score": sub(ra.get("drought"), rb.get("drought")),
        "irrigation_need": sub(ra.get("irrigation_need"), rb.get("irrigation_need")),
        "aqi": sub(ca.get("aqi"), cb.get("aqi")),
        "soil": sub(ca.get("soil_moisture_m3m3"), cb.get("soil_moisture_m3m3")),
    }

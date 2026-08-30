"""IMD-style heat wave, high wind, heavy rain guidance from members."""

from __future__ import annotations

from typing import Any

from app.ml.hybrid_blend import RAIN_HEAVY_MM, RAIN_VERY_HEAVY_MM, p_exceed


def _series(members: dict, key: str, i: int) -> tuple[list[str], list[float]]:
    ids, vals = [], []
    for sid, pack in members.items():
        ser = pack.get(key) or []
        if i < len(ser):
            ids.append(sid)
            vals.append(float(ser[i]))
    return ids, vals


LEVELS = {
    "quiet": "No alert",
    "outlook": "Possible",
    "watch": "Warning",
}


def _level(key: str) -> dict[str, str]:
    return {"level": LEVELS.get(key, key), "level_key": key}


def run(
    f: dict[str, Any],
    members: dict[str, dict],
    weights: dict[str, float],
    fusion: dict[str, Any],
    blend_hourly: list[float] | None = None,
) -> dict[str, Any]:
    tmax = [float(x) for x in (f.get("temp_max") or [])[:7]]
    wind_d = [float(x) for x in (f.get("wind_max") or [])[:7]]
    hourly_wind = [float(x) for x in (f.get("hourly_wind") or f.get("hourly_wind_kmh") or [])[:48]]
    hourly_temp = [float(x) for x in (f.get("hourly_temp") or [])[:48]]
    hourly_rain = [float(x) for x in (f.get("hourly_precip") or [])[:48]]
    clim = float(f.get("clim_tmax_c") or 35.0)

    heat_days = []
    for i, tx in enumerate(tmax):
        if tx >= 40.0 or (clim and tx >= clim + 4.5):
            heat_days.append(i)
    consecutive = 0
    best_run = 0
    for i in range(len(tmax)):
        if i in heat_days:
            consecutive += 1
            best_run = max(best_run, consecutive)
        else:
            consecutive = 0
    p_heat = 0.0
    if members:
        hits = 0
        n = 0
        for sid, pack in members.items():
            ser = pack.get("temp_max") or []
            if len(ser) >= 2:
                n += 1
                if sum(1 for v in ser[:3] if float(v) >= 40) >= 2:
                    hits += 1
        p_heat = hits / n if n else (1.0 if best_run >= 2 else 0.35 if heat_days else 0.05)

    wind_peak = max(hourly_wind) if hourly_wind else (max(wind_d) if wind_d else 0.0)
    wind_h = None
    if hourly_wind:
        wind_h = int(max(range(len(hourly_wind)), key=lambda i: hourly_wind[i]))
    p_wind = 0.0
    if wind_peak >= 60:
        p_wind = 0.75
    elif wind_peak >= 40:
        p_wind = 0.4
    elif wind_peak >= 30:
        p_wind = 0.15

    if hourly_rain:
        rain24 = sum(hourly_rain[:24])
    else:
        pd = f.get("precip_days") or [0.0]
        rain24 = float(pd[0] or 0.0)
    ids0, vals0 = _series(members, "precip_days", 0)
    ww = [float(weights.get(s, 1.0)) for s in ids0] if ids0 else None
    p_heavy = fusion.get("extremes", {}).get("p_ge_64_5")
    if p_heavy is None:
        p_heavy = p_exceed(vals0, RAIN_HEAVY_MM, ww) if vals0 else (1.0 if rain24 >= RAIN_HEAVY_MM else 0.0)

    heat_key = "watch" if best_run >= 2 else ("outlook" if heat_days else "quiet")
    wind_key = "watch" if wind_peak >= 60 else ("outlook" if wind_peak >= 40 else "quiet")
    rain_key = "watch" if (p_heavy or 0) >= 0.3 or rain24 >= RAIN_HEAVY_MM else ("outlook" if rain24 >= 25 else "quiet")
    blend = [float(x) for x in (blend_hourly or [])[:48]]
    compare = []
    n = max(len(hourly_rain), len(blend), 48)
    for i in range(min(48, n)):
        compare.append(
            {
                "h": i,
                "blend_mm": round(blend[i], 2) if i < len(blend) else None,
                "website_mm": round(hourly_rain[i], 2) if i < len(hourly_rain) else None,
                "website_temp_c": round(hourly_temp[i], 1) if i < len(hourly_temp) else None,
                "website_wind_kmh": round(hourly_wind[i], 1) if i < len(hourly_wind) else None,
            }
        )
    return {
        "guidance_only": True,
        "heat_wave": {
            **_level(heat_key),
            "p": round(p_heat, 3),
            "tmax_c": round(max(tmax), 1) if tmax else None,
            "days_ge_40": len(heat_days),
            "consecutive": best_run,
            "hourly_temp_c": [round(x, 1) for x in hourly_temp[:48]],
            "rule": "IMD-style: Tmax ≥40 °C or ≥4.5 °C above clim, ≥2 days — guidance",
        },
        "high_wind": {
            **_level(wind_key),
            "p": round(p_wind, 3),
            "peak_kmh": round(wind_peak, 1),
            "peak_hour": wind_h,
            "hourly_kmh": [round(x, 1) for x in hourly_wind[:48]],
            "rule": "Peak 10 m wind ≥60 km/h watch, ≥40 km/h outlook — next 48 h",
        },
        "heavy_rain": {
            **_level(rain_key),
            "p": round(float(p_heavy or 0), 3),
            "p_very_heavy": fusion.get("extremes", {}).get("p_ge_115_6"),
            "next_24h_mm": round(float(rain24 or 0), 1),
            "threshold_mm": RAIN_HEAVY_MM,
            "very_heavy_mm": RAIN_VERY_HEAVY_MM,
            "hourly_mm": [round(x, 2) for x in hourly_rain[:48]],
            "rule": "IMD heavy ≥64.5 mm/day; very heavy ≥115.6 mm/day",
        },
        "compare": {
            "note": "Blend = gated mix of physics and AI members. Website = Open-Meteo. This is not the satellite Ensemble series.",
            "hourly": compare,
        },
    }

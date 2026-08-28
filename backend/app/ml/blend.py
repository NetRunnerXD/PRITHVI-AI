"""RainFall residual-blend model.

Trusted series = Open-Meteo / GloFAS raw values.
Ours = same backbone + soil persistence, climatology pull, and anomaly bias.
The LLM never computes these numbers.
"""

from __future__ import annotations

from statistics import mean
from typing import Any


def _clip(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))


def _nudge_precip(
    p: float,
    day_i: int,
    soil: float,
    clim_daily: float,
    precip_z: float,
    atlas_frac: float = 0.0,
) -> tuple[float, str]:
    """Stay close to the trusted Open-Meteo backbone; only small residuals."""
    reasons: list[str] = []
    adj = float(p)
    if soil >= 0.33:
        adj *= 1.03
        reasons.append("wet-soil persistence +3%")
    elif soil <= 0.20:
        adj *= 0.97
        reasons.append("dry-soil suppression −3%")
    if precip_z >= 1.3 and day_i <= 2:
        adj *= 1.04
        reasons.append("wet anomaly +4%")
    elif precip_z <= -1.1 and day_i <= 2:
        adj *= 0.97
        reasons.append("dry anomaly −3%")
    if day_i >= 4 and clim_daily > 0:
        pull = 0.08
        adj = adj * (1 - pull) + clim_daily * pull
        reasons.append("light climatology pull 8%")
    if atlas_frac:
        adj *= 1.0 + atlas_frac
        reasons.append(f"India residual atlas {atlas_frac:+.0%}")
    band = max(2.0, abs(p) * 0.12)
    adj = _clip(adj, max(0.0, p - band), p + band)
    return round(adj, 1), "; ".join(reasons) or "pass-through"


def build_dual_predictions(f: dict[str, Any]) -> dict[str, Any]:
    precip = [float(x) for x in (f.get("precip_days") or [])][:7]
    probs = [int(x) for x in (f.get("precip_prob") or [])][:7]
    tmax = [float(x) for x in (f.get("temp_max") or [])][:7]
    tmin = [float(x) for x in (f.get("temp_min") or [])][:7]
    et0 = [float(x) for x in (f.get("et0_days") or [])][:7]
    times = [str(x) for x in (f.get("daily_times") or [])][:7]
    n = min(7, max(len(precip), len(times)))
    soil = float(f.get("soil_m3m3") or 0.28)
    clim = float(f.get("clim_daily_mm") or 6.0)
    z = float(f.get("precip_z") or 0.0)
    from app.ml.features import past_window

    hourly = [float(x) for x in past_window(f.get("hourly_precip") or [], int(f.get("hourly_now_i") or 0), 6)]
    persist = mean(hourly) * 6 if hourly else 0.0
    from app.science.residual import atlas_lookup, monsoon_regime

    regime = monsoon_regime(f)
    lat = f.get("lat")
    lon = f.get("lon")

    trusted_days: list[dict[str, Any]] = []
    ours_days: list[dict[str, Any]] = []
    soil_t, soil_o = soil, soil
    notes: list[str] = []

    for i in range(n):
        p = precip[i] if i < len(precip) else 0.0
        e = et0[i] if i < len(et0) else 3.0
        pr = probs[i] if i < len(probs) else 0
        tx = tmax[i] if i < len(tmax) else None
        tn = tmin[i] if i < len(tmin) else None
        date = times[i] if i < len(times) else f"d+{i}"
        soil_t = _clip(soil_t + p * 0.0035 - e * 0.0075, 0.12, 0.45)
        hit = atlas_lookup(lat, lon, regime, i)
        p_hat, why = _nudge_precip(p, i, soil, clim, z, atlas_frac=float(hit.get("frac") or 0))
        if i == 0 and persist >= 6:
            extra = min(2.0, persist * 0.08)
            p_hat = round(p_hat + extra, 1)
            why = (why + "; " if why else "") + "recent hourly pulse"
        soil_o = _clip(soil_o + p_hat * 0.0035 - e * 0.0075, 0.12, 0.45)
        conf_t = max(55, 92 - i * 5)
        conf_o = max(48, 86 - i * 6)
        if why:
            notes.append(f"{date}: {why}")
        trusted_days.append(
            {
                "date": date,
                "precip_mm": round(p, 1),
                "precip_prob_pct": pr,
                "temp_max_c": round(tx, 1) if tx is not None else None,
                "temp_min_c": round(tn, 1) if tn is not None else None,
                "et0_mm": round(e, 2),
                "soil_m3m3": round(soil_t, 3),
                "water_balance_mm": round(p - e, 2),
                "irrigate": p < 4 and soil_t < 0.26 and pr < 55,
                "flood_watch": p >= 25,
                "confidence_pct": conf_t,
            }
        )
        ours_days.append(
            {
                "date": date,
                "precip_mm": p_hat,
                "precip_prob_pct": int(_clip(pr + (8 if p_hat > p else -5), 5, 99)),
                "temp_max_c": round(tx, 1) if tx is not None else None,
                "temp_min_c": round(tn, 1) if tn is not None else None,
                "et0_mm": round(e, 2),
                "soil_m3m3": round(soil_o, 3),
                "water_balance_mm": round(p_hat - e, 2),
                "irrigate": p_hat < 4 and soil_o < 0.26 and pr < 55,
                "flood_watch": p_hat >= 22,
                "confidence_pct": conf_o,
                "adjustment": why,
            }
        )

    def pack(days: list[dict[str, Any]], source: str, method: str) -> dict[str, Any]:
        rains = [d["precip_mm"] for d in days]
        et = [d["et0_mm"] for d in days]
        return {
            "source": source,
            "method": method,
            "days": days,
            "precip_3d_mm": round(sum(rains[:3]), 1),
            "precip_7d_mm": round(sum(rains), 1),
            "et0_7d_mm": round(sum(et), 2),
            "water_balance_7d_mm": round(sum(rains) - sum(et), 1),
            "irrigate_dates": [d["date"] for d in days if d.get("irrigate")],
            "flood_watch_dates": [d["date"] for d in days if d.get("flood_watch")],
        }

    return {
        "trusted": pack(
            trusted_days,
            "Open-Meteo (ECMWF / best-match)",
            "Raw published forecast — no local residual",
        ),
        "ours": pack(
            ours_days,
            "Rituchakra residual-blend v4",
            "Trusted Open-Meteo backbone + ±12% residual (soil / anomaly / India atlas)",
        ),
        "adjustments": notes,
        "inputs": {
            "soil_m3m3": soil,
            "clim_daily_mm": clim,
            "precip_z": round(z, 2),
            "hourly_pulse_mm": round(persist, 2),
            "atlas_regime": regime,
        },
    }

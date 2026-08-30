"""RainFall residual-blend model.

Trusted series = Open-Meteo / GloFAS raw values.
Ours = same backbone + soil persistence, climatology pull, and anomaly bias.
The LLM never computes these numbers.
"""

from __future__ import annotations

from statistics import mean
from typing import Any

from app.ml.hybrid_blend import (
    RAIN_EXTREME_MM,
    RAIN_HEAVY_MM,
    RAIN_VERY_HEAVY_MM,
    day_members,
    equal_weights,
    p_exceed,
    vincentize,
)


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
    members = f.get("members") if isinstance(f.get("members"), dict) else {}
    member_ids = [k for k, v in members.items() if isinstance(v, dict)]
    wmap = equal_weights(member_ids) if member_ids else {}
    vera_w = f.get("vera_gate_weights")
    if isinstance(vera_w, dict) and member_ids:
        merged = {sid: float(vera_w.get(sid, wmap.get(sid, 0))) for sid in member_ids}
        s = sum(merged.values()) or 1.0
        wmap = {k: round(v / s, 4) for k, v in merged.items()}
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
        q = None
        p_backbone = p
        ids_i, vals_i = day_members(members, i) if members else ([], [])
        if vals_i:
            ww = [wmap.get(s, 1.0 / len(vals_i)) for s in ids_i]
            q = vincentize(vals_i, ww)
            p_backbone = float(q["q50"])
        soil_t = _clip(soil_t + p * 0.0035 - e * 0.0075, 0.12, 0.45)
        hit = atlas_lookup(lat, lon, regime, i)
        p_hat, why = _nudge_precip(p_backbone, i, soil, clim, z, atlas_frac=float(hit.get("frac") or 0))
        if q is not None:
            why = (why + "; " if why else "") + f"hybrid CDF q50 (not mean {q['mean']:.1f} mm)"
            pr = int(_clip(q["pop"] * 100, 5, 99))
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
                "precip_q10_mm": round(q["q10"], 1) if q else None,
                "precip_q50_mm": round(q["q50"], 1) if q else None,
                "precip_q90_mm": round(q["q90"], 1) if q else None,
                "p_heavy": round(p_exceed(vals_i, RAIN_HEAVY_MM, [wmap[s] for s in ids_i]), 3) if vals_i else None,
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
            "Rituchakra hybrid AI–NWP blend v5",
            "Vincentized multi-model CDF q50 + ±12% residual (soil / anomaly / India atlas). Rain field is q50, not mean mm.",
        ),
        "adjustments": notes,
        "inputs": {
            "soil_m3m3": soil,
            "clim_daily_mm": clim,
            "precip_z": round(z, 2),
            "hourly_pulse_mm": round(persist, 2),
            "atlas_regime": regime,
        },
        "hybrid": _hybrid_pack(ours_days, member_ids, wmap, members, times, n),
    }


def _hybrid_pack(
    ours_days: list[dict[str, Any]],
    member_ids: list[str],
    wmap: dict[str, float],
    members: dict,
    times: list,
    n: int,
) -> dict[str, Any]:
    day0_ids, day0_vals = day_members(members, 0) if members else ([], [])
    ww0 = [wmap.get(s, 0) for s in day0_ids] if day0_ids else []
    return {
        "method": "vera_moe_vincentize",
        "guidance_only": True,
        "rain_day": "03:00Z/03:00Z",
        "members": member_ids,
        "weights": wmap,
        "attribution": "Forecast data from Open-Meteo (CC BY 4.0); models ECMWF/NOAA/DWD.",
        "hazards": {
            "guidance_only": True,
            "heavy_rain": {
                "p": round(p_exceed(day0_vals, RAIN_HEAVY_MM, ww0), 3) if day0_vals else None,
                "threshold_mm": RAIN_HEAVY_MM,
                "cdf": "vincentized_24h",
            },
            "very_heavy_rain": {
                "p": round(p_exceed(day0_vals, RAIN_VERY_HEAVY_MM, ww0), 3) if day0_vals else None,
                "threshold_mm": RAIN_VERY_HEAVY_MM,
            },
            "extreme_rain": {
                "p": round(p_exceed(day0_vals, RAIN_EXTREME_MM, ww0), 3) if day0_vals else None,
                "threshold_mm": RAIN_EXTREME_MM,
            },
        },
        "days": [
            {
                "date": d.get("date"),
                "q10": d.get("precip_q10_mm"),
                "q50": d.get("precip_q50_mm"),
                "q90": d.get("precip_q90_mm"),
                "p_heavy": d.get("p_heavy"),
            }
            for d in ours_days
        ],
    }

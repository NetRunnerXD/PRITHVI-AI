"""Soil–rain hysteresis. Same mm does different work on wetting vs drying limbs."""

from __future__ import annotations

from typing import Any


def _clip(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))


def initial_state(f: dict[str, Any]) -> dict[str, Any]:
    from app.ml.features import past_window

    soil = float(f.get("soil_m3m3") or 0.28)
    today = float(f.get("precip_today_mm") or 0)
    hourly = [float(x) for x in past_window(f.get("hourly_precip") or [], int(f.get("hourly_now_i") or 0), 24)]
    pulse = sum(hourly)
    memory = _clip((soil - 0.16) / 0.28 + min(pulse, 25) / 80, 0.0, 1.0)
    limb = "wetting" if today >= 4 or pulse >= 6 or soil >= 0.32 else "drying"
    return {
        "soil": _clip(soil, 0.12, 0.45),
        "memory": round(memory, 3),
        "limb": limb,
        "runoff_mm": 0.0,
        "infil_mm": 0.0,
        "et_mm": 0.0,
    }


def step_day(state: dict[str, Any], precip_mm: float, et0_mm: float) -> dict[str, Any]:
    soil = float(state["soil"])
    memory = float(state["memory"])
    p = max(0.0, float(precip_mm))
    e = max(0.0, float(et0_mm))
    limb = "wetting" if p >= e * 0.8 and p >= 2.0 else "drying"
    wet0 = float(state.get("_infil_wet") or 0.48)
    dry0 = float(state.get("_infil_dry") or 0.72)
    if limb == "wetting":
        # Wet limb: pores already occupied → more runoff, less storage.
        infil_eff = _clip(wet0 + 0.40 * (1 - soil / 0.45) * (1 - 0.55 * memory), 0.18, 0.92)
        et_eff = _clip(0.55 + 0.25 * (soil - 0.16) / 0.29, 0.40, 0.90)
    else:
        # Dry limb: clay/silt holds water; ET pulls slower from residual.
        infil_eff = _clip(dry0 + 0.22 * (1 - soil / 0.45), 0.45, 0.96)
        et_eff = _clip(0.70 + 0.20 * memory, 0.55, 0.95)
    infil = p * infil_eff
    runoff = p - infil
    et = e * et_eff
    ds = infil * 0.0035 - et * 0.0075
    soil2 = _clip(soil + ds, 0.12, 0.45)
    mem2 = _clip(0.72 * memory + 0.28 * _clip((soil2 - 0.16) / 0.28, 0, 1), 0, 1)
    return {
        "soil": soil2,
        "memory": round(mem2, 3),
        "limb": limb,
        "runoff_mm": round(runoff, 2),
        "infil_mm": round(infil, 2),
        "et_mm": round(et, 2),
        "_infil_wet": state.get("_infil_wet"),
        "_infil_dry": state.get("_infil_dry"),
    }


def fingerprint(f: dict[str, Any]) -> dict[str, Any]:
    """Walk the 7-day horizon and summarise the loop."""
    from app.science.soil import classify

    soil = classify(f.get("lat"), f.get("lon"))
    st = initial_state(f)
    if soil.get("infil_wet"):
        st["_infil_wet"] = soil["infil_wet"]
        st["_infil_dry"] = soil["infil_dry"]
    precip = list(f.get("precip_days") or [])
    et0 = list(f.get("et0_days") or [])
    times = list(f.get("daily_times") or [])
    n = min(7, max(len(precip), 1))
    days: list[dict[str, Any]] = []
    runoff_7 = 0.0
    for i in range(n):
        p = float(precip[i]) if i < len(precip) else 0.0
        e = float(et0[i]) if i < len(et0) else 3.0
        st = step_day(st, p, e)
        runoff_7 += st["runoff_mm"]
        days.append(
            {
                "date": str(times[i]) if i < len(times) else f"d+{i}",
                "limb": st["limb"],
                "soil_m3m3": round(st["soil"], 3),
                "memory": st["memory"],
                "runoff_mm": st["runoff_mm"],
                "infil_mm": st["infil_mm"],
            }
        )
    flip = "runoff" if st["memory"] >= 0.62 and any(d["limb"] == "wetting" for d in days[:3]) else "absorbing"
    return {
        "limb": days[0]["limb"] if days else st["limb"],
        "memory": days[0]["memory"] if days else st["memory"],
        "soil_now": round(float(f.get("soil_m3m3") or st["soil"]), 3),
        "runoff_3d_mm": round(sum(d["runoff_mm"] for d in days[:3]), 2),
        "runoff_7d_mm": round(runoff_7, 2),
        "flip": flip,
        "days": days,
        "soil_class": soil,
        "method": f"dual-limb soil hysteresis v1 ({soil.get('id')})",
    }

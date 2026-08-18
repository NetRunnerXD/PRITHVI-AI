"""Plot water-budget ledger. Conservation-closed 0–7 cm twin."""

from __future__ import annotations

from typing import Any


def week(f: dict[str, Any], hy: dict[str, Any], plot_m2: float) -> dict[str, Any]:
    precip = list(f.get("precip_days") or [])
    et0 = list(f.get("et0_days") or [])
    times = list(f.get("daily_times") or [])
    days = hy.get("days") or []
    rows = []
    for i, d in enumerate(days[:7]):
        p = float(precip[i]) if i < len(precip) else float(d.get("infil_mm") or 0) + float(d.get("runoff_mm") or 0)
        e = float(et0[i]) if i < len(et0) else 3.0
        q = float(d.get("runoff_mm") or 0)
        infil = float(d.get("infil_mm") or max(0.0, p - q))
        ds = infil * 0.25 - e * 0.35
        u = p - e - q - ds
        rows.append(
            {
                "date": d.get("date") or (times[i] if i < len(times) else f"d+{i}"),
                "precip_mm": round(p, 2),
                "et0_mm": round(e, 2),
                "runoff_mm": round(q, 2),
                "delta_soil_mm": round(ds, 2),
                "unobserved_mm": round(u, 2),
                "liters": int(round(plot_m2 * p)),
            }
        )
    return {
        "plot_m2": plot_m2,
        "days": rows,
        "identity": "P - ET0 - Q - ΔS - U ≈ 0",
        "method": "plot ledger v1",
    }

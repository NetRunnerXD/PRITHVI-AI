"""Multi-resolution temporal fusion 0–10 days."""

from __future__ import annotations

from typing import Any


def sat_weight(lead_h: float) -> float:
    if lead_h <= 2:
        return 0.70
    if lead_h <= 6:
        return 0.55
    if lead_h <= 24:
        return 0.22
    if lead_h <= 72:
        return 0.10
    return 0.05


def run(
    cv: dict[str, Any],
    fusion: dict[str, Any],
    gate: dict[str, Any],
    historical: dict[str, Any],
    hourly_om: list[float],
) -> dict[str, Any]:
    est = float((cv.get("derived") or {}).get("precip_est_mmh") or 0)
    q50 = float(fusion.get("q50") or 0)
    clim = float((historical.get("climatology") or {}).get("harmonic_doy") or 6)
    hourly = []
    for h in range(48):
        sw = sat_weight(h + 0.5)
        nwp = hourly_om[h] if h < len(hourly_om) else q50 / 24.0
        val = sw * est + (1 - sw) * float(nwp)
        if h >= 24:
            val = 0.7 * val + 0.3 * (clim / 24.0)
        hourly.append(round(max(0.0, val), 3))
    windows = {
        "nowcast_0_6": {
            "dominant": "satellite CV / ConvLSTM",
            "sat_w": 0.7,
            "mm": round(sum(hourly[:6]), 2),
        },
        "short_6_48": {
            "dominant": "NWP + AI blend; satellite as condition",
            "sat_w": 0.22,
            "mm": round(sum(hourly[6:48]), 2),
        },
        "medium_2_10": {
            "dominant": "AI models + regime + climatology",
            "sat_w": 0.05,
            "mm": round(q50 * 8, 2),
        },
    }
    curve = [{"lead_h": h, "sat_w": round(sat_weight(h), 3), "nwp_w": round(1 - sat_weight(h), 3)} for h in (1, 3, 6, 12, 24, 48, 72, 120, 240)]
    return {
        "windows": windows,
        "seamless": curve,
        "hourly_0_48": hourly,
        "p10": [round(v * 0.45, 3) for v in hourly],
        "p90": [round(v * 1.85, 3) for v in hourly],
        "by_window_weights": gate.get("by_window"),
    }

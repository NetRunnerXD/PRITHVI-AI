"""Outdoor labour WBGT proxy. Not a globe thermometer."""

from __future__ import annotations

from typing import Any


def estimate(temp_c: float, rh: float, wind_ms: float | None = None) -> dict[str, Any]:
    t = float(temp_c)
    h = max(0.0, min(100.0, float(rh)))
    # Simplified outdoor WBGT (ABM / ACSM-style) without black globe.
    e = (h / 100.0) * 6.105 * pow(2.71828, 17.27 * t / (237.7 + t))
    wbgt = 0.567 * t + 0.393 * e + 3.94
    if wind_ms is not None and float(wind_ms) >= 3:
        wbgt -= 0.4
    wbgt = max(18.0, min(40.0, wbgt))
    level = "stop" if wbgt >= 32 else "limit" if wbgt >= 28 else "caution" if wbgt >= 26 else "ok"
    return {
        "wbgt_c": round(wbgt, 1),
        "level": level,
        "method": "simplified outdoor WBGT v1 (no globe)",
        "note": "Proxy from T and RH. Not a WBGT instrument.",
    }

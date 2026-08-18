"""District monsoon clock — complementary to seasonal onset SMS, not a clone."""

from __future__ import annotations

from typing import Any

from app.science.residual import monsoon_regime


def clock(f: dict[str, Any]) -> dict[str, Any]:
    reg = monsoon_regime(f)
    z = float(f.get("precip_z") or 0)
    rain3 = float(f.get("precip_3d_mm") or 0)
    label = {
        "pre": "pre-monsoon",
        "active": "active monsoon",
        "break": "monsoon break",
        "post": "withdrawal",
        "winter": "winter / dry",
    }.get(reg, reg)
    return {
        "regime": reg,
        "label": label,
        "precip_z": round(z, 2),
        "rain_3d_mm": round(rain3, 1),
        "note": "Local regime from NASA POWER z + 3-day rain. Area guidance, not a sowing date.",
        "method": "district monsoon clock v1",
    }

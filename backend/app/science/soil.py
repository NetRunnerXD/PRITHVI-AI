"""India soil-family prior for hysteresis. One Gangetic number is not India."""

from __future__ import annotations

from typing import Any


def classify(lat: float | None, lon: float | None) -> dict[str, Any]:
    if lat is None or lon is None:
        return {"id": "gangetic_alluvium", "infil_wet": 0.48, "infil_dry": 0.72}
    la, lo = float(lat), float(lon)
    if 21.4 <= la <= 23.2 and 87.4 <= lo <= 89.2:
        return {
            "id": "delta_clay_haldia",
            "infil_wet": 0.40,
            "infil_dry": 0.62,
            "note": "Hugli / Purba Medinipur clay-silt. Ponds more than upland alluvium.",
        }
    if 21.5 <= la <= 27.8 and 84.5 <= lo <= 89.8:
        return {"id": "gangetic_alluvium", "infil_wet": 0.48, "infil_dry": 0.72}
    if 18.0 <= la <= 26.5 and 73.0 <= lo <= 81.5 and la < 22.5:
        return {"id": "black_cotton", "infil_wet": 0.32, "infil_dry": 0.55}
    if 8.0 <= la <= 16.5 and 74.5 <= lo <= 80.5:
        return {"id": "laterite", "infil_wet": 0.55, "infil_dry": 0.80}
    if 24.5 <= la <= 30.5 and 69.5 <= lo <= 76.5:
        return {"id": "arid_alluvium", "infil_wet": 0.60, "infil_dry": 0.88}
    return {"id": "peninsula_default", "infil_wet": 0.48, "infil_dry": 0.72}

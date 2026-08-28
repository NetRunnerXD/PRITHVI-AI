"""Water-balance–identified attribution. Factors must sit in a conservation identity."""

from __future__ import annotations

from typing import Any


def attribute(f: dict[str, Any], hy: dict[str, Any]) -> dict[str, Any]:
    precip = float(f.get("precip_3d_mm") or 0)
    et0 = sum(float(x) for x in (f.get("et0_days") or [f.get("et0_today") or 3])[:3])
    runoff = float(hy.get("runoff_3d_mm") or 0)
    infil = max(0.0, precip - runoff)
    soil0 = float(f.get("soil_m3m3") or 0.28)
    # 0–7 cm storage change ≈ infil*0.0035*1000 depth-mm equivalent of the layer.
    d_soil_mm = infil * 0.25 - et0 * 0.35
    # Residual closes the budget: deep percolation + unobserved.
    residual = precip - et0 - runoff - d_soil_mm
    parts = {
        "precip_mm": round(precip, 2),
        "et0_mm": round(et0, 2),
        "runoff_mm": round(runoff, 2),
        "delta_soil_mm": round(d_soil_mm, 2),
        "deep_plus_unobserved_mm": round(residual, 2),
    }
    checksum = parts["precip_mm"] - parts["et0_mm"] - parts["runoff_mm"] - parts["delta_soil_mm"] - parts["deep_plus_unobserved_mm"]
    return {
        "identity": "P - ET0 - runoff - Δsoil = U (U is the residual, not a measured flux)",
        "parts": parts,
        "checksum_mm": round(checksum, 3),
        "soil_m3m3": soil0,
        "method": "3-day water-balance residual v1",
        "note": "ΔS is a 0–7 cm proxy (infil×0.25 − ET0×0.35). U closes the arithmetic, not a soil column.",
    }

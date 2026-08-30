"""Common-grid remap, quantile mapping, hourly alignment, imputation."""

from __future__ import annotations

from typing import Any


def quantile_map(x: float, src_mean: float, src_std: float, tgt_mean: float, tgt_std: float) -> float:
    s = src_std if src_std > 1e-6 else 1.0
    z = (x - src_mean) / s
    return tgt_mean + z * (tgt_std if tgt_std > 1e-6 else 1.0)


def align_hourly(series: list[float], native_hours: float, out_hours: int = 48) -> list[float]:
    if not series:
        return [0.0] * out_hours
    step = max(native_hours, 0.25)
    out: list[float] = []
    t = 0.0
    i = 0
    while len(out) < out_hours:
        while i + 1 < len(series) and (i + 1) * step <= t:
            i += 1
        out.append(float(series[min(i, len(series) - 1)]))
        t += 1.0
    return out


def impute(vals: list[float | None]) -> list[float]:
    out: list[float] = []
    last = 0.0
    for v in vals:
        if v is None:
            out.append(last)
        else:
            last = float(v)
            out.append(last)
    return out


def remap_note(lat: float, lon: float) -> dict[str, Any]:
    return {
        "grid": "0.25° India pin + 9×9 neighbourhood",
        "alt_grid": "0.1° nowcast",
        "lat": round(lat, 4),
        "lon": round(lon, 4),
        "bias": "quantile mapping vs NASA POWER / ERA5-like clim",
        "temporal": "hourly alignment 0–48 h",
    }

"""S5-C2: scale precip in code. LLM only quotes the scaled pack."""

from __future__ import annotations

import re
from typing import Any

_DOUBLE = re.compile(r"\b(double|twice|2\s*[x×]|two times|what if .{0,40}rain)\b", re.I)
_SCALE = re.compile(r"\b(\d+(?:\.\d+)?)\s*[x×]\b", re.I)

SCALE_MIN, SCALE_MAX = 0.25, 4.0


def detect_scale(text_en: str) -> float | None:
    t = text_en or ""
    m = _SCALE.search(t)
    if m:
        try:
            s = float(m.group(1))
        except ValueError:
            s = None
        else:
            if SCALE_MIN <= s <= SCALE_MAX:
                return s
            return None
    if re.search(r"\b(double[sd]?|twice|two times)\b", t, re.I) and re.search(
        r"\brain|precip", t, re.I
    ):
        return 2.0
    return None


def _scale_num(v: Any, factor: float) -> Any:
    if isinstance(v, bool) or v is None:
        return v
    if isinstance(v, (int, float)):
        return round(float(v) * factor, 2)
    return v


def scale_forecast(pack: dict[str, Any], factor: float) -> dict[str, Any]:
    factor = max(SCALE_MIN, min(SCALE_MAX, float(factor)))
    out = dict(pack)
    for k in ("precip_next_3d_mm", "precip_7d_mm", "precip_1h_mm", "water_balance_7d_mm"):
        if k in out and isinstance(out[k], (int, float)):
            out[k] = _scale_num(out[k], factor)
    days = []
    for row in out.get("outlook_days") or []:
        if not isinstance(row, dict):
            days.append(row)
            continue
        d = dict(row)
        if isinstance(d.get("precip_mm"), (int, float)):
            d["precip_mm"] = round(float(d["precip_mm"]) * factor, 2)
            d["irrigate"] = bool(d["precip_mm"] < 4.0 and float(d.get("soil_m3m3") or 0.3) < 0.26)
            d["flood_watch"] = bool(d["precip_mm"] >= 25.0)
        days.append(d)
    if days:
        out["outlook_days"] = days
    out["counterfactual_scale"] = factor
    out["need"] = pack.get("need") or "forecast"
    out["note"] = f"Precip scaled ×{factor} in code (counterfactual). Not a second model run."
    return out

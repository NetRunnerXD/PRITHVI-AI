"""Equal-weight Vincentization of multi-model daily precip.

Operational rain is CDF q50, never the arithmetic mean of millimetres.
"""

from __future__ import annotations

from typing import Any

from app.ml.features import _daily, _start_today

RAIN_HEAVY_MM = 64.5
RAIN_VERY_HEAVY_MM = 115.5
RAIN_EXTREME_MM = 204.5


def vincentize(values: list[float], weights: list[float] | None = None) -> dict[str, float]:
    pairs = [(float(v), 1.0) for v in values if v is not None]
    if weights is not None and len(weights) == len(values):
        pairs = [(float(v), float(w)) for v, w in zip(values, weights) if v is not None]
    if not pairs:
        return {"q10": 0.0, "q50": 0.0, "q90": 0.0, "pop": 0.0, "mean": 0.0}
    tot = sum(w for _, w in pairs) or 1.0
    pairs = [(v, w / tot) for v, w in pairs]
    pairs.sort(key=lambda x: x[0])
    cdf = 0.0
    qs: dict[float, float] = {}
    targets = [0.1, 0.5, 0.9]
    for v, w in pairs:
        cdf += w
        for t in targets:
            if t not in qs and cdf + 1e-12 >= t:
                qs[t] = v
    last = pairs[-1][0]
    for t in targets:
        qs.setdefault(t, last)
    pop = sum(w for v, w in pairs if v > 0)
    mean = sum(v * w for v, w in pairs)
    return {"q10": qs[0.1], "q50": qs[0.5], "q90": qs[0.9], "pop": pop, "mean": mean}


def p_exceed(values: list[float], threshold: float, weights: list[float] | None = None) -> float:
    if not values:
        return 0.0
    w = weights if weights and len(weights) == len(values) else [1.0] * len(values)
    tot = sum(w) or 1.0
    return sum((wi / tot) for v, wi in zip(values, w) if v >= threshold)


def equal_weights(ids: list[str]) -> dict[str, float]:
    n = max(len(ids), 1)
    return {i: round(1.0 / n, 4) for i in ids}


def member_daily_from_om(om: dict[str, Any]) -> dict[str, list]:
    times = list((om.get("daily") or {}).get("time") or [])
    start = _start_today(times)
    return {
        "daily_times": times[start:],
        "precip_days": _daily(om, "precipitation_sum")[start:],
        "precip_prob": [int(p) for p in _daily(om, "precipitation_probability_max")[start:]],
        "temp_max": _daily(om, "temperature_2m_max")[start:],
        "temp_min": _daily(om, "temperature_2m_min")[start:],
        "wind_max": _daily(om, "wind_speed_10m_max")[start:],
    }


def day_members(members: dict[str, dict], i: int, key: str = "precip_days") -> tuple[list[str], list[float]]:
    ids: list[str] = []
    vals: list[float] = []
    for sid, pack in members.items():
        series = pack.get(key) or []
        if i < len(series):
            ids.append(sid)
            vals.append(float(series[i]))
    return ids, vals

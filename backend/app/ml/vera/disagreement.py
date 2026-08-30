"""Model disagreement index: high impact / low confidence flags."""

from __future__ import annotations

import math
from typing import Any


def _stdev(xs: list[float]) -> float:
    if len(xs) < 2:
        return 0.0
    mu = sum(xs) / len(xs)
    return math.sqrt(sum((x - mu) ** 2 for x in xs) / len(xs))


def _index(xs: list[float]) -> float:
    if not xs:
        return 0.0
    mu = abs(sum(xs) / len(xs)) + 1.0
    return round(min(1.0, _stdev(xs) / mu), 3)


def run(members: dict[str, dict], fusion: dict[str, Any], leads: list[dict[str, Any]]) -> dict[str, Any]:
    day0 = []
    tmax0 = []
    wind0 = []
    for pack in members.values():
        p = pack.get("precip_days") or []
        if p:
            day0.append(float(p[0]))
        t = pack.get("temp_max") or []
        if t:
            tmax0.append(float(t[0]))
        w = pack.get("wind_max") or []
        if w:
            wind0.append(float(w[0]))
    rain_i = _index(day0)
    temp_i = _index(tmax0)
    wind_i = _index(wind0)
    p_heavy = float((fusion.get("extremes") or {}).get("p_ge_64_5") or 0)
    rain_q50 = float(fusion.get("q50") or 0)
    flags = []
    if rain_i >= 0.35 and (p_heavy >= 0.2 or rain_q50 >= 25):
        flags.append(
            {
                "id": "rain_hilc",
                "title": "High impact / low confidence — rain",
                "detail": "Members disagree on tomorrow’s rain while the blend is wet or P(≥64.5 mm) is material.",
                "index": rain_i,
            }
        )
    if temp_i >= 0.25 and (max(tmax0) if tmax0 else 0) >= 38:
        flags.append(
            {
                "id": "heat_hilc",
                "title": "High impact / low confidence — heat",
                "detail": "Models split on how hot the next day gets.",
                "index": temp_i,
            }
        )
    if wind_i >= 0.3 and (max(wind0) if wind0 else 0) >= 40:
        flags.append(
            {
                "id": "wind_hilc",
                "title": "High impact / low confidence — wind",
                "detail": "Gust/speed spread is large on a windy signal.",
                "index": wind_i,
            }
        )
    by_lead = []
    for row in leads:
        by_lead.append(
            {
                "lead_h": row.get("lead_h"),
                "rain_range": [row.get("rain", {}).get("q10"), row.get("rain", {}).get("q90")],
                "flag": bool((row.get("rain") or {}).get("q90") and (row.get("rain") or {}).get("q10") is not None
                             and float((row["rain"].get("q90") or 0) - (row["rain"].get("q10") or 0)) >= 40),
            }
        )
    return {
        "rain": rain_i,
        "temp": temp_i,
        "wind": wind_i,
        "member_rain": {"min": min(day0) if day0 else None, "max": max(day0) if day0 else None, "n": len(day0)},
        "flags": flags,
        "by_lead": by_lead,
        "note": "Index is member spread / (|mean|+1). Flag when spread is large and the event looks high-impact.",
    }

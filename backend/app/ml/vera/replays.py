"""Canned case-study replays. Historical illustration, not live IMD archive."""

from __future__ import annotations

from typing import Any

CASES: list[dict[str, Any]] = [
    {
        "id": "monsoon_deluge",
        "title": "Monsoon deluge (illustration)",
        "place": "Howrah, West Bengal",
        "date": "2026-07-21",
        "kind": "heavy rain",
        "blend_mm": 92.0,
        "best_member_mm": 61.0,
        "equal_mm": 54.0,
        "website_mm": 48.0,
        "p_heavy": 0.62,
        "disagreement": 0.41,
        "signal": "Blend crossed the IMD heavy-rain line 18 h earlier than the driest member.",
        "note": "Synthetic replay from member spread + regime prior. Not a reanalysis of a named storm.",
    },
    {
        "id": "heat_wave",
        "title": "Heat-wave days (illustration)",
        "place": "Jaipur, Rajasthan",
        "date": "2026-05-29",
        "kind": "heat",
        "blend_tmax_c": 43.2,
        "best_member_tmax_c": 41.0,
        "website_tmax_c": 40.4,
        "p_ge_40": 0.78,
        "disagreement": 0.22,
        "signal": "Tail-weighted heat members kept Tmax ≥40 °C for three days while a cool GFS outlier did not.",
        "note": "Illustration of the heat branch, not an official IMD heat-wave bulletin.",
    },
    {
        "id": "cyclone_wind",
        "title": "Cyclone-adjacent wind (illustration)",
        "place": "Puri, Odisha",
        "date": "2025-10-28",
        "kind": "wind",
        "blend_kmh": 68.0,
        "best_member_kmh": 55.0,
        "website_kmh": 52.0,
        "p_ge_60": 0.44,
        "disagreement": 0.38,
        "signal": "Disagreement flag fired while ICON/GFS split; blend stayed on the windy side of 60 km/h.",
        "note": "Guidance illustration. Not a cyclone track product.",
    },
]


def run() -> dict[str, Any]:
    return {"cases": CASES, "kind": "historical illustration"}

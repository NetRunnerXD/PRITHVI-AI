"""S4: spreading activation over data() capabilities. α=0.6, depth 3."""

from __future__ import annotations

from collections import defaultdict

NODES = (
    "forecast",
    "nowcast",
    "rain_window",
    "aqi",
    "quality",
    "mandi",
    "warnings",
    "risks",
    "rank",
    "states_weather",
    "compare",
    "capability",
    "place_search",
)

# directed composition edges
_EDGES: dict[str, tuple[str, ...]] = {
    "forecast": ("nowcast", "rain_window", "risks"),
    "nowcast": ("forecast", "warnings"),
    "rain_window": ("forecast",),
    "aqi": ("quality", "risks"),
    "quality": ("aqi", "forecast"),
    "mandi": ("forecast",),
    "warnings": ("nowcast", "risks"),
    "risks": ("forecast", "warnings", "aqi"),
    "rank": ("states_weather",),
    "states_weather": ("rank",),
    "compare": ("forecast",),
}

_SEEDS = {
    "nowcast": ("pump", "next hour", "next 2", "onset", "field access", "nowcast"),
    "forecast": ("outlook", "7 day", "temperature", "weather", "rain"),
    "rain_window": ("from ", " to ", "between ", "mm on", "august", "september"),
    "aqi": ("aqi", "air quality", "pollution", "pm2"),
    "quality": ("pollen", "uv index", "dew point", "all metrics", "every parameter"),
    "mandi": ("mandi", "quintal", "modal"),
    "warnings": ("warning", "alert", "tsunami", "earthquake", "imd"),
    "risks": ("flood risk", "drought", "heat risk"),
    "rank": ("rank", "which district", "worst flood"),
    "states_weather": ("all india", "states"),
    "compare": (" vs ", "versus", "compare"),
    "capability": ("radar", "insat", "gauge", "ncs"),
}

ALPHA = 0.6
DEPTH = 3
TOP_K = 8
TAU_LOW = 0.45


def seed_scores(text_en: str, needs: list[str]) -> dict[str, float]:
    t = (text_en or "").lower()
    scores: dict[str, float] = defaultdict(float)
    for n in needs:
        if n in NODES:
            scores[n] = max(scores[n], 1.0)
    for node, kws in _SEEDS.items():
        if any(k in t for k in kws):
            scores[node] = max(scores[node], 0.9)
    return dict(scores)


def activate(seeds: dict[str, float]) -> dict[str, float]:
    energy = dict(seeds)
    frontier = dict(seeds)
    for _ in range(DEPTH):
        nxt: dict[str, float] = defaultdict(float)
        for node, e in frontier.items():
            for nb in _EDGES.get(node, ()):
                nxt[nb] += e * ALPHA
        for n, e in nxt.items():
            energy[n] = max(energy.get(n, 0.0), e)
        frontier = dict(nxt)
        if not frontier:
            break
    return energy


def route(text_en: str, needs: list[str]) -> tuple[list[str], float]:
    seeds = seed_scores(text_en, needs)
    if not seeds and needs:
        seeds = {n: 1.0 for n in needs if n in NODES}
    energy = activate(seeds) if seeds else {}
    ranked = sorted(energy.items(), key=lambda kv: -kv[1])
    top = [n for n, s in ranked if s >= TAU_LOW][:TOP_K]
    peak = ranked[0][1] if ranked else 0.0
    if needs:
        return list(dict.fromkeys([n for n in needs if n in NODES or True])), max(peak, 1.0)
    return top, peak

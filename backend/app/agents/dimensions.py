"""Multi-axis hints for a question. Not a single exclusive intent."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from app.agents.dates import parse_window
from app.data.india_districts import extract_place, extract_places, match_state
from app.data.india_towns import extract_town, extract_towns
from app.science.vernacular import observe_speech

_INTENT_WORDS = {
    "rank": [
        "which district", "which districts", "list them", "list the district",
        "most likely", "more likely", "rank", "ranking", "worst hit",
        "prone", "highest flood", "most flood", "কোন কোন জেলা", "कौन से जिले",
    ],
    "list": [
        "all district", "all districts", "all cities", "all city", "list all",
        "list district", "list state", "every district", "gazetteer",
    ],
    "irrigation": [
        "irrigat", "sech", "সেচ", "सिंचाई", "sinchai", "water the", "should i water",
        "field water", "पानी देना", "pump", "পাম্প", "पंप",
    ],
    "rain": [
        "rain", "precip", "বৃষ্টি", "बारिश", "वर्षा", "monsoon", "বর্ষা",
        "shower", "downpour",
    ],
    "flood": ["flood", "বন্যা", "बाढ़", "inundat", "waterlog", "জলাবদ্ধ", "নদী আসছে", "নদী ভাঙ"],
    "seismic": ["earthquake", "quake", "seismic", "भूकंप", "ভূমিকম্প", "aftershock"],
    "tsunami": ["tsunami", "সুনামি", "सुनामी", "itews"],
    "marine": ["marine", "wave height", "swell", "sea state", "समुद्री", "সমুদ্র তরঙ্গ"],
    "drought": ["drought", "খরা", "सूखा", "dry spell", "deficit"],
    "heat": ["heat", "গরম", "गर्मी", "heatwave", "তাপদাহ", "hot day"],
    "aqi": ["aqi", "air quality", "pollution", "smog", "pm2", "प्रदूषण", "দূষণ"],
    "price": ["mandi", "price", "bhav", "भाव", "দাম", "মূল্য", "rate", "agmark"],
    "compare": ["compare", "versus", " vs ", "तुलना", "তুলনা", "difference between"],
    "outlook": ["7 day", "seven day", "week", "outlook", "আগামী সপ্তাহ", "अगला सप्ताह", "water balance"],
    "window": [
        "show me", "prediction", "forecast for", "between", " to the ",
        "till", "until", "from the", "date range", "next 5", "next 6", "next 7",
    ],
    "crop": ["crop", "ফসল", "फसल", "rice", "ধান", "wheat", "vegetab"],
}

_NOWCAST_WORDS = (
    "hour", "hours", "tonight", "nowcast", "onset", "next 2", "next two",
    "0-6", "pump", "field", "should i start", "enter the field",
)

_LENS_WORDS = {
    "happening": ("what is happening", "right now", "current", "live", "এখন", "अभी"),
    "why": ("why", "because", "driver", "anomaly", "কেন", "क्यों"),
    "next": ("will", "next", "outlook", "forecast", "আগামী", "अगला"),
    "do": ("should i", "what should", "advise", "pump", "irrigat", "করণীয়", "क्या करूँ"),
}

_FOLLOW = re.compile(
    r"\b(there|same|that place|same for|what about|and the|how about)\b",
    re.I,
)

ALWAYS_SCHEMAS = {
    "present_answer",
    "switch_location",
    "get_rain_window",
    "get_nowcast",
    "compare_districts",
    "geo_search",
    "capability",
}

_HINT_SCHEMAS: dict[str, set[str]] = {
    "rank": {"list_districts", "rank_districts"},
    "list": {"list_states", "list_districts"},
    "irrigation": {
        "get_nowcast", "get_weather_forecast", "get_soil_moisture",
        "get_prescriptions", "get_water_balance", "get_science_pack",
    },
    "rain": {
        "get_nowcast", "get_rain_window", "get_weather_forecast",
        "get_7day_outlook", "get_science_pack",
    },
    "flood": {
        "get_imd_warnings", "get_nowcast", "get_flood_outlook",
        "get_hazard_watch", "get_science_pack",
    },
    "seismic": {"get_hazard_watch"},
    "tsunami": {"get_hazard_watch"},
    "marine": {"get_hazard_watch", "get_weather_forecast"},
    "drought": {"get_weather_forecast", "get_water_balance"},
    "heat": {"get_weather_forecast"},
    "aqi": {"get_air_quality"},
    "price": {"get_mandi_prices", "get_state_mandi"},
    "compare": {"compare_districts"},
    "outlook": {"get_nowcast", "get_rain_window", "get_7day_outlook", "get_water_balance", "get_science_pack"},
    "window": {"get_rain_window", "get_7day_outlook"},
    "crop": {"retrieve_playbook", "get_mandi_prices", "get_science_pack"},
    "general": {"get_nowcast", "get_weather_forecast", "get_imd_warnings", "get_hazard_watch"},
}


@dataclass
class Dimensions:
    tags: set[str] = field(default_factory=set)
    places: list[str] = field(default_factory=list)
    window: dict[str, Any] | None = None
    lenses: list[str] = field(default_factory=list)
    scope: str | None = None
    primary: str = "general"
    follow_up: bool = False

    def as_dict(self) -> dict[str, Any]:
        win = None
        if self.window:
            start, end = self.window.get("start"), self.window.get("end")
            win = {
                "start": start.isoformat() if hasattr(start, "isoformat") else start,
                "end": end.isoformat() if hasattr(end, "isoformat") else end,
                "kind": self.window.get("kind"),
            }
        return {
            "tags": sorted(self.tags),
            "places": self.places,
            "window": win,
            "lenses": self.lenses,
            "scope": self.scope,
            "primary": self.primary,
            "follow_up": self.follow_up,
        }


def extract_state(text: str) -> str | None:
    return match_state(text or "")


def mentioned_place(text: str) -> str | None:
    places = mentioned_places(text)
    return places[0] if places else None


def mentioned_places(text: str) -> list[str]:
    blob = text or ""
    low = blob.lower()
    towns = extract_towns(blob)
    out: list[str] = []
    seen: set[str] = set()
    for name in towns:
        key = name.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(name)
    for name in extract_places(blob):
        key = name.lower()
        if key in seen:
            continue
        # Keep alias/fuzzy hits (Puruliya → Purulia even though "purulia" is not in the text).
        seen.add(key)
        out.append(name)
    return out


def extract_compare_other(text: str, focus: str | None = None) -> str | None:
    places = mentioned_places(text)
    focus_l = (focus or "").lower()
    rest = [p for p in places if p.lower() != focus_l]
    if len(places) >= 2:
        if focus_l and places[0].lower() == focus_l:
            return places[1]
        return rest[-1] if rest else places[-1]
    if rest:
        return rest[0]
    return None


def extract_metric(text: str) -> str:
    t = (text or "").lower()
    if any(w in t for w in ("drought", "খরা", "सूखा", "dry")):
        return "drought"
    if any(w in t for w in ("heat", "গরম", "गर्मी")):
        return "heat"
    if any(w in t for w in ("irrigat", "সেচ", "सिंचाई")):
        return "irrigation"
    if any(w in t for w in ("price", "mandi", "দাম", "भाव")):
        return "price"
    if any(w in t for w in ("rain", "বৃষ্টি", "बारिश")) and "flood" not in t:
        return "rain"
    return "flood"


def _hit_counts(text: str) -> dict[str, int]:
    t = (text or "").lower()
    hits: dict[str, int] = {}
    for intent, words in _INTENT_WORDS.items():
        hits[intent] = sum(1 for w in words if w in t)
    tags = set(observe_speech(text).get("tags") or [])
    if tags & {"river_rise", "flood", "waterlog", "tide"} and not hits.get("irrigation"):
        hits["flood"] = hits.get("flood", 0) + 1
    if tags & {"irrigate"}:
        hits["irrigation"] = hits.get("irrigation", 0) + 1
    if tags & {"dry_spell"}:
        hits["drought"] = hits.get("drought", 0) + 1
    if tags & {"heat"}:
        hits["heat"] = hits.get("heat", 0) + 1
    return hits


def classify(text: str) -> str:
    """Single primary label — kept for templates and existing tests."""
    t = (text or "").lower()
    hits = _hit_counts(text)
    if hits.get("rank") or (
        hits.get("flood") and any(w in t for w in ("which", "list", "district", "জেলা", "जिला"))
    ):
        return "rank"
    if hits.get("list"):
        return "list"
    best = max(hits, key=hits.get)
    if hits[best] == 0:
        return "general"
    if hits["compare"]:
        return "compare"
    if hits["irrigation"] and hits["rain"]:
        return "irrigation"
    if parse_window(t) and (
        hits.get("rain") or hits.get("outlook") or hits.get("window") or hits.get("heat") or "forecast" in t
    ):
        return "window"
    return best


def _lenses(text: str, tags: set[str]) -> list[str]:
    t = (text or "").lower()
    found: list[str] = []
    for lens, words in _LENS_WORDS.items():
        if any(w in t for w in words):
            found.append(lens)
    if "irrigation" in tags or "flood" in tags:
        if "do" not in found:
            found.append("do")
    if tags & {"rain", "outlook", "window", "heat"}:
        if "next" not in found:
            found.append("next")
    if tags & {"aqi", "flood", "marine", "seismic", "tsunami"}:
        if "happening" not in found:
            found.append("happening")
    if not found:
        found.append("happening")
    return found


def hint_dimensions(text: str) -> Dimensions:
    hits = _hit_counts(text)
    tags = {k for k, n in hits.items() if n}
    window = parse_window(text)
    if window:
        tags.add("window")
    primary = classify(text)
    scope = None
    if primary in {"compare", "rank", "list"}:
        scope = primary
    elif "compare" in tags:
        scope = "compare"
    elif "rank" in tags:
        scope = "rank"
    elif "list" in tags:
        scope = "list"
    return Dimensions(
        tags=tags,
        places=mentioned_places(text),
        window=window,
        lenses=_lenses(text, tags),
        scope=scope,
        primary=primary,
        follow_up=bool(_FOLLOW.search(text or "")),
    )


def merge_followup(current: Dimensions, prior: Dimensions | None) -> Dimensions:
    if prior is None or not current.follow_up:
        return current
    if not current.places:
        current.places = list(prior.places)
    if current.window is None:
        current.window = prior.window
    if not current.tags:
        current.tags = set(prior.tags)
        current.primary = prior.primary
        current.scope = prior.scope
        current.lenses = list(prior.lenses)
    elif prior.tags:
        current.tags |= {t for t in prior.tags if t not in {"compare", "rank", "list"}}
    return current


def required_tools(intent: str) -> list[str]:
    """Full pack for an old-style intent (tests + documentation)."""
    packs = {
        "rank": ["list_districts", "rank_districts"],
        "list": ["list_states", "list_districts"],
        "irrigation": [
            "get_nowcast", "get_weather_forecast", "get_soil_moisture",
            "get_prescriptions", "get_water_balance", "get_science_pack",
        ],
        "rain": ["get_nowcast", "get_rain_window", "get_weather_forecast", "get_7day_outlook", "get_science_pack"],
        "flood": [
            "get_imd_warnings", "get_nowcast", "get_flood_outlook",
            "get_hazard_watch", "rank_districts", "get_science_pack",
        ],
        "seismic": ["get_hazard_watch"],
        "tsunami": ["get_hazard_watch"],
        "marine": ["get_hazard_watch", "get_weather_forecast"],
        "drought": ["get_weather_forecast", "get_water_balance"],
        "heat": ["get_weather_forecast"],
        "aqi": ["get_air_quality"],
        "price": ["get_mandi_prices", "get_state_mandi"],
        "compare": ["compare_districts"],
        "outlook": ["get_nowcast", "get_rain_window", "get_7day_outlook", "get_water_balance", "get_science_pack"],
        "window": ["get_rain_window", "get_7day_outlook"],
        "crop": ["retrieve_playbook", "get_mandi_prices", "get_science_pack"],
        "general": ["get_nowcast", "get_weather_forecast", "get_imd_warnings", "get_hazard_watch", "get_science_pack"],
    }
    return list(packs.get(intent, packs["general"]))


def wants_nowcast(dims: Dimensions, text: str) -> bool:
    t = (text or "").lower()
    if dims.tags & {"irrigation", "flood"}:
        return True
    if "rain" in dims.tags and any(w in t for w in _NOWCAST_WORDS):
        return True
    if any(w in t for w in _NOWCAST_WORDS):
        return True
    return False


def safety_tools(dims: Dimensions, text: str) -> list[str]:
    """Minimum evidence to inject. The agent may call more."""
    need: list[str] = []

    def add(name: str) -> None:
        if name not in need:
            need.append(name)

    if wants_nowcast(dims, text) or "rain" in dims.tags:
        add("get_nowcast")
    rainish = bool(dims.tags & {"rain", "outlook", "window", "heat", "irrigation"}) or "forecast" in (text or "").lower()
    if dims.window and rainish:
        add("get_rain_window")
    if dims.scope == "rank":
        add("list_districts")
        add("rank_districts")
    if dims.scope == "list":
        add("list_states")
        add("list_districts")
    if dims.scope == "compare" and extract_compare_other(text, dims.places[0] if dims.places else None):
        add("compare_districts")
    if "aqi" in dims.tags:
        add("get_air_quality")
    if "price" in dims.tags:
        add("get_mandi_prices")
    if dims.tags & {"seismic", "tsunami", "marine"}:
        add("get_hazard_watch")
    if "flood" in dims.tags and dims.scope != "rank":
        add("get_imd_warnings")
        add("get_flood_outlook")
        add("get_hazard_watch")
    if "irrigation" in dims.tags:
        add("get_prescriptions")
        add("get_soil_moisture")
    return need


def schema_names(dims: Dimensions) -> set[str]:
    names = set(ALWAYS_SCHEMAS)
    for tag in dims.tags | {dims.primary}:
        names |= _HINT_SCHEMAS.get(tag, set())
    if dims.scope == "rank":
        names |= _HINT_SCHEMAS["rank"]
    return names


def looks_like_place(text: str) -> bool | str:
    m = re.search(r"\b(?:in|at|near|vs|versus)\s+([A-Z][a-zA-Z]+(?:\s+[A-Z][a-zA-Z]+)?)", text or "")
    if m:
        return m.group(1)
    return False

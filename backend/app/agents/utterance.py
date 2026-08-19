"""Classify any human chat line: topic + Indian place (fuzzy) + refuse unknown.

A bare name (Puruliya) is a request for conditions at the resolved Indian place.
A fictitious or foreign name (Atlantis, Hogwarts, Paris) is a refuse — never invent
weather and never fall back to the dashboard pin.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from app.agents.dates import parse_window
from app.data.blocked_places import FOREIGN, FICTION, is_blocked_name
from app.data.india_districts import is_state_name, match_states
from app.services.location_svc import resolve_named_place

_RAIN = ("rain", "precip", "shower", "monsoon", "rainfall", "downpour", "mm ")
_NOW = ("nowcast", "next 2", "next two", "hour", "hours", "tonight", "pump", "onset", "should i irrigat", "irrigate now")
_AQI = ("aqi", "air quality", "pollution", "pm2", "smog")
_MANDI = ("mandi", "agmark", "quintal", "modal price")
_WARN = ("warning", "imd cap", "alert", "tsunami", "earthquake", "quake")
_FORE = ("7 day", "seven day", "outlook", "next 3 day", "next three", "week ahead")
_RANK = ("rank", "ranking", "which district", "worst", "most flood", "prone")
_VISIT = ("visit", "tourist", "tourism", "holiday", "vacation", "trip", "best place", "best places")
_PET = ("pet", "dog", "cat", "elephant", "tiger", "puppy", "animal")
_PET_ACT = ("take", "island", "islands", "outing", "walk", "zoo", "safari", "bring")
_WX_NOW = ("weather", "temperature", "temp ", "how is the sky", "current condition", "conditions in")
_OFF = (
    "recipe", "poem", "world cup", "cricket score",
    "movie", "joke", "capital of france", "hello", "hi there", "who are you",
    "times 19", "17 times",
)
_QWORDS = (
    "what", "where", "how", "why", "who", "when", "should", "could",
    "would", "can", "will", "about", "which", "whose",
)
_CHAT_STOP = re.compile(
    r"\b(hello|hi|hey|thanks|thank you|please|yes|yeah|yep|no|nope|ok|okay)\b",
    re.I,
)
_PREP = re.compile(
    r"\b(?:in|at|near|around|for|of)\s+"
    r"([A-Za-z][A-Za-z .'-]{0,40}?)"
    r"(?=\s*[?.!,;]|$|\s+(?:today|tomorrow|tonight|now|please|and|or|vs|versus|"
    r"this|next|from|to|on|are|is|was|were|will|that|which|more|list|how)\b)",
    re.I,
)
_WX_PLACE = re.compile(
    r"^([A-Za-z][A-Za-z .'-]{1,40}?)\s+(?:weather|forecast|aqi|rain|temperature|conditions)\b",
    re.I,
)
_PLACE_WX = re.compile(
    r"\b(?:weather|forecast|aqi|rain|temperature|conditions)\s+(?:in|at|for|near)?\s*"
    r"([A-Za-z][A-Za-z .'-]{1,40}?)\s*$",
    re.I,
)
_ABOUT_PLACE = re.compile(
    r"^\s*(?:how about|what about|and(?: then)?|also|try|check)\s+"
    r"([A-Za-z][A-Za-z .'-]{1,40}?)\s*[?.!]?\s*$",
    re.I,
)
_STOP_HEAD = {
    "the", "my", "a", "an", "this", "that", "these", "those",
    "next", "last", "past", "coming", "few", "some", "any",
    "india", "indian", "weather", "rain", "aqi", "flood",
    "hours", "hour", "days", "day", "week", "mm",
}

# Place-level packs Rituchakra can actually compute. Used for "all metrics".
CATALOG_NEEDS = ("forecast", "nowcast", "aqi", "warnings", "risks", "mandi", "capability")

_AFFIRM = {
    "yes", "yeah", "yep", "yup", "sure", "ok", "okay", "please",
    "go ahead", "go on", "continue", "do it", "all of them", "all of it",
    "all", "everything", "the rest", "more", "more details", "those too",
    "both", "the others", "all metrics", "every metric",
}
_FOLLOW_WORDS = {
    "all", "them", "these", "those", "both", "rest", "more", "everything",
    "details", "of", "the", "it", "this", "that", "please", "yes", "yeah",
    "ok", "okay", "sure",
}
_CATALOG_PHRASES = (
    "all metric", "every metric", "metrics present", "all data",
    "everything you have", "full pack", "complete picture",
    "list all metric", "list the metric", "what metrics",
    "all of them", "all of it", "every data", "available metric",
)


@dataclass
class Plan:
    """What to do with one user line."""

    mode: str  # chat | data | refuse
    needs: list[str] = field(default_factory=list)
    states: list[str] = field(default_factory=list)
    refuse: str | None = None
    asked: str | None = None
    unknown_place: bool = False
    needs_geocode: bool = False
    follow: bool = False
    catalog: bool = False


def _norm_line(text: str) -> str:
    return re.sub(r"[^\w\s]", "", (text or "").lower()).strip()


def is_followup_affirm(text: str) -> bool:
    """Yes / all of them / more details — continue the last place, not a new town."""
    return _norm_line(text) in _AFFIRM


def wants_catalog(text: str) -> bool:
    """Human asked for every Rituchakra metric, not one figure."""
    t = (text or "").lower()
    if is_followup_affirm(text) and _norm_line(text) in {
        "all of them", "all of it", "all", "everything", "all metrics", "every metric", "the rest",
    }:
        return True
    if any(p in t for p in _CATALOG_PHRASES):
        return True
    if "metric" in t and any(w in t for w in ("all", "every", "list", "present", "available")):
        return True
    return False


def looks_like_bare_place(text: str) -> bool:
    """A 1–3 token utterance that is probably just a place name."""
    raw = (text or "").strip()
    if not raw or len(raw) > 48:
        return False
    if is_followup_affirm(raw) or wants_catalog(raw):
        return False
    words = re.findall(r"[A-Za-z]+", raw)
    if not words or len(words) > 3:
        return False
    if all(w.lower() in _FOLLOW_WORDS for w in words):
        return False
    blob = raw.lower()
    if any(w in blob for w in _OFF + _PET + _VISIT + _RAIN + _AQI + _NOW + _FORE + _WARN + _RANK + _MANDI + _WX_NOW):
        return False
    if any(w.lower() in _QWORDS for w in words):
        return False
    if _CHAT_STOP.search(raw):
        return False
    return True


def unknown_refuse(name: str) -> str:
    shown = (name or "that name").strip()
    return (
        f"“{shown}” is not a place in the Rituchakra Indian gazetteer "
        "(and I will not invent weather, AQI, or flood figures for a made-up or foreign name). "
        "Name an Indian town or district — for example Purulia, Puri, or Cherrapunji."
    )


def _usable_span(span: str | None) -> str | None:
    if not span:
        return None
    words = [w for w in re.findall(r"[A-Za-z]+", span) if w.lower() not in _STOP_HEAD]
    if not words:
        return None
    return " ".join(words)


def _looks_like_name(span: str | None) -> bool:
    """False for 'how much', 'will it', 'what is the' — those are not places."""
    words = re.findall(r"[A-Za-z]+", span or "")
    if not words:
        return False
    if any(w.lower() in _QWORDS for w in words):
        return False
    if any(w.lower() in {"much", "many", "about", "it", "them", "there"} for w in words):
        return False
    return True


def is_place_retarget(text: str) -> bool:
    """'How about Malda' / 'what about Puri' is a request for that place, not chit-chat."""
    raw = (text or "").strip()
    if looks_like_bare_place(raw):
        return True
    if _ABOUT_PLACE.match(raw) and len(raw.split()) <= 6:
        return True
    return False


def extract_asked_span(text: str) -> str | None:
    """The place-like span the human pointed at, even if it is fictitious."""
    raw = (text or "").strip()
    if not raw:
        return None
    if looks_like_bare_place(raw):
        return raw
    from app.agents.dimensions import mentioned_place

    known = mentioned_place(raw)
    if known:
        return known
    about = _ABOUT_PLACE.match(raw)
    if about:
        span = _usable_span(about.group(1))
        if span and _looks_like_name(span):
            return span
    hits = list(_PREP.finditer(raw))
    for m in reversed(hits):
        span = _usable_span(m.group(1))
        if span and _looks_like_name(span):
            return span
    for rx in (_WX_PLACE, _PLACE_WX):
        m = rx.search(raw)
        if not m:
            continue
        span = _usable_span(m.group(1))
        if span and _looks_like_name(span):
            return span
    return None


def interpret(text: str) -> Plan:
    """Refuse unsourced metrics. Fetch only named product needs. Resolve fuzzy Indian names."""
    from app.agents.dimensions import mentioned_place

    t = (text or "").lower()
    states = match_states(text)
    rain = any(w in t for w in _RAIN)
    visit = any(w in t for w in _VISIT)
    pet = any(w in t for w in _PET)
    wx = (
        rain
        or any(w in t for w in _AQI + _NOW + _FORE + _WARN + _RANK + _MANDI + _WX_NOW)
        or "flood" in t
        or "heat" in t
    )

    catalog = wants_catalog(text)
    follow = is_followup_affirm(text)

    asked = extract_asked_span(text) or mentioned_place(text)
    if asked is None and looks_like_bare_place(text):
        asked = (text or "").strip()
    resolved = resolve_named_place(asked) if asked else None
    state_only = bool(asked and is_state_name(asked)) or (
        looks_like_bare_place(text) and bool(states) and resolved is None
    )
    blocked = is_blocked_name(asked)

    if follow or (catalog and not asked and not resolved):
        needs = list(CATALOG_NEEDS) if catalog else []
        return Plan(
            mode="data" if needs else "chat",
            needs=needs,
            asked=asked,
            follow=True,
            catalog=catalog,
        )

    if catalog and (resolved or asked):
        return Plan(
            mode="data",
            needs=list(CATALOG_NEEDS),
            states=states,
            asked=asked,
            catalog=True,
            needs_geocode=bool(asked and not resolved),
        )

    if any(
        p in t
        for p in (
            "best to visit",
            "best places to visit",
            "best places to take",
            "best states to visit",
            "best cities to visit",
        )
    ):
        return Plan(
            mode="refuse",
            asked=asked,
            refuse=(
                "Rituchakra does not rank tourist appeal or 'best places to visit'. "
                "I can rank Indian states or districts by 3-day rain, flood score, or heat from Open-Meteo + local-ml. "
                "Name that metric if you want it."
            ),
        )
    if pet and (visit or any(w in t for w in _PET_ACT)):
        return Plan(
            mode="refuse",
            asked=asked,
            refuse=(
                "Rituchakra has no pet-visit, island-outing, or animal-care index. "
                "I will not invent whether you should take an elephant anywhere. "
                "Ask for rain, heat, flood score, or CPCB AQI at a named Indian town if you want those figures."
            ),
        )
    if visit and not wx and not states:
        return Plan(
            mode="refuse",
            asked=asked,
            refuse=(
                "Rituchakra does not rank tourist appeal or 'best places to visit'. "
                "I can rank Indian states or districts by 3-day rain, flood score, or heat from Open-Meteo + local-ml. "
                "Name a metric I actually store."
            ),
        )
    if visit and states and not wx and "flood" not in t and "rain" not in t:
        return Plan(mode="data", needs=["states_weather"], states=states, asked=asked)

    place_attempt = bool(asked) and (
        is_blocked_name(asked)
        or looks_like_bare_place(text)
        or _looks_like_name(asked)
    )
    if blocked:
        return Plan(
            mode="refuse",
            asked=asked,
            unknown_place=True,
            refuse=unknown_refuse(asked or text or "that name"),
        )
    if (
        asked
        and not resolved
        and not state_only
        and place_attempt
        and (looks_like_bare_place(text) or wx)
    ):
        # Not in the local gazetteer — still an Indian-looking name. Geocode, then fetch.
        return Plan(
            mode="data",
            needs=["forecast"] if (looks_like_bare_place(text) or wx) else [],
            states=states,
            asked=asked,
            needs_geocode=True,
        )

    if looks_like_bare_place(text):
        if resolved:
            return Plan(mode="data", needs=["forecast"], states=states, asked=asked)
        if state_only:
            # Capital table should have resolved this; if not, geocode the state name.
            return Plan(
                mode="data",
                needs=["forecast"],
                states=states or match_states(asked or text),
                asked=asked,
                needs_geocode=True,
            )
        return Plan(
            mode="data",
            needs=["forecast"],
            asked=asked,
            needs_geocode=True,
        )

    if any(w in t for w in _OFF) and not wx:
        return Plan(mode="chat", states=states, asked=asked)

    needs: list[str] = []
    win = parse_window(text)
    if rain and win:
        needs.append("rain_window")
    if any(w in t for w in _FORE) or any(w in t for w in _WX_NOW) or (
        rain and any(w in t for w in ("how much", "how many", "prediction", "forecast")) and not win
    ):
        needs.append("forecast")
    if any(w in t for w in _NOW) or (rain and any(w in t for w in ("irrigat", "pump", "sech", "field"))):
        needs.append("nowcast")
    if any(w in t for w in _AQI):
        needs.append("aqi")
    if any(w in t for w in _MANDI) or ("price" in t and any(w in t for w in ("rice", "paddy", "wheat", "onion", "potato"))):
        needs.append("mandi")
    if any(w in t for w in _WARN) and not rain:
        needs.append("warnings")
    if any(w in t for w in ("driest", "drought", "dry spell")) and (states or "which" in t or any(w in t for w in _RANK)):
        needs.append("rank")
    if "flood" in t and (any(w in t for w in _RANK) or "which" in t or states):
        needs.append("rank")
    elif "flood" in t:
        needs.append("warnings")
        needs.append("nowcast")
        needs.append("risks")
    if any(w in t for w in ("compare", " versus ", " vs ", " or ")) and (wx or len(states) >= 2):
        if len(states) >= 2:
            if "states_weather" not in needs:
                needs.append("states_weather")
        else:
            needs.append("compare")
    if visit and wx and "states_weather" not in needs and (states or "list" in t or "best" in t):
        needs.append("states_weather")
    if any(w in t for w in ("radar", "insat", "rain-gauge", "rain gauge", "ncs live")):
        needs.append("capability")
    if "list" in t and ("state" in t or "district" in t or "cities" in t or "city" in t) and (wx or visit):
        if visit and not wx:
            return Plan(
                mode="refuse",
                asked=asked,
                refuse=(
                    "I cannot list the best Indian states or cities to visit. "
                    "That is not a Rituchakra dataset. "
                    "Ask for a flood, rain, or heat ranking and I will use Open-Meteo + local-ml."
                ),
                states=states,
            )
        if "states_weather" not in needs:
            needs.append("states_weather")

    # Named place + weather words, or a geocode candidate with no other need
    if wx and not needs:
        if resolved:
            needs.append("forecast")
        elif asked and _looks_like_name(asked):
            needs.append("forecast")

    seen: set[str] = set()
    out: list[str] = []
    for n in needs:
        if n not in seen:
            seen.add(n)
            out.append(n)
    if out:
        return Plan(
            mode="data",
            needs=out,
            states=states,
            asked=asked,
            needs_geocode=bool(asked and not resolved and not state_only),
        )
    if (resolved or asked) and is_place_retarget(text):
        # "what about Kerala?" after a rank is a state follow-up, not a capital forecast.
        if is_state_name(asked or "") and not looks_like_bare_place(text):
            return Plan(mode="chat", states=states or match_states(asked or text), asked=asked)
        return Plan(
            mode="data",
            needs=["forecast"],
            states=states,
            asked=asked,
            needs_geocode=bool(asked and not resolved),
        )
    return Plan(mode="chat", states=states, asked=asked)

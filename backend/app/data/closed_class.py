"""Tokens that are never Indian place names: calendar, deixis, units, products."""

from __future__ import annotations

import re

from app.data.fuzzy import fold

CALENDAR = {
    "today", "tomorrow", "tonight", "yesterday", "weekend", "week", "month",
    "morning", "evening", "afternoon", "night", "now", "later", "soon",
    "monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday",
    "january", "february", "march", "april", "may", "june", "july", "august",
    "september", "october", "november", "december",
    "jan", "feb", "mar", "apr", "jun", "jul", "aug", "sep", "sept", "oct", "nov", "dec",
}

DEIXIS = {
    "there", "here", "same", "it", "them", "that", "this", "these", "those",
    "and", "also", "more", "then", "the", "a", "an", "my", "our", "please",
    "yes", "yeah", "yep", "ok", "okay", "sure",
}

PRODUCT = {
    "mm", "aqi", "rain", "rainfall", "weather", "forecast", "outlook",
    "hours", "hour", "days", "day", "temperature", "temp", "conditions",
    "nowcast", "warning", "alert", "flood", "heat", "mandi", "metric",
    "metrics", "data", "all",
}

CLOSED = CALENDAR | DEIXIS | PRODUCT

_WS = re.compile(r"\s+")


def tokens_of(text: str) -> list[str]:
    return [t for t in re.findall(r"[A-Za-z]+", text or "") if t]


def is_closed_token(word: str | None) -> bool:
    w = fold(word or "")
    if not w:
        return False
    return w in CLOSED or (word or "").strip().lower() in CLOSED


def is_closed_query(text: str | None) -> bool:
    """True when the whole string is calendar/deixis/product, not a town."""
    words = tokens_of(text or "")
    if not words:
        return False
    return all(is_closed_token(w) for w in words)


# Follow-up fragments only. "forecast for tomorrow" is a full question, not inherit-only.
_TIME_FOLLOW = CALENDAR | {
    "what", "how", "about", "and", "for", "on", "the", "this", "next",
    "coming", "please", "will", "it", "also", "then", "try", "check",
    "there", "same", "here", "weekend", "week", "am", "pm", "at",
}


def is_time_only(text: str | None) -> bool:
    """'tomorrow', 'and tomorrow', 'what about tomorrow', 'this weekend' — not 'weather today'."""
    from app.agents.dates import parse_window

    raw = _WS.sub(" ", (text or "").strip())
    if not raw:
        return False
    if parse_window(raw) is None:
        return False
    words = tokens_of(raw)
    if not words:
        return False
    return all(w.lower() in _TIME_FOLLOW for w in words)

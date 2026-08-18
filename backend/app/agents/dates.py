"""Parse calendar windows from user questions. Year defaults from today (IST)."""

from __future__ import annotations

import re
from datetime import date, timedelta
from typing import Any

from app.science.nowcast import IST, _now

_MONTHS = {
    "january": 1, "jan": 1,
    "february": 2, "feb": 2,
    "march": 3, "mar": 3,
    "april": 4, "apr": 4,
    "may": 5,
    "june": 6, "jun": 6,
    "july": 7, "jul": 7,
    "august": 8, "aug": 8,
    "september": 9, "sep": 9, "sept": 9,
    "october": 10, "oct": 10,
    "november": 11, "nov": 11,
    "december": 12, "dec": 12,
}

_ORD = re.compile(r"(\d{1,2})(?:st|nd|rd|th)?", re.I)


def today_ist() -> date:
    return _now().date()


def _year_for(month: int, day: int, today: date) -> int:
    try:
        cand = date(today.year, month, day)
    except ValueError:
        return today.year
    if cand < today - timedelta(days=3) and month < today.month:
        return today.year + 1
    return today.year


def _mk(year: int, month: int, day: int) -> date | None:
    try:
        return date(year, month, day)
    except ValueError:
        return None


def parse_window(text: str, today: date | None = None) -> dict[str, Any] | None:
    """Return {start, end, kind} as date objects, or None."""
    today = today or today_ist()
    raw = " ".join((text or "").lower().replace("—", " ").replace("–", "-").split())
    if not raw:
        return None

    m = re.search(
        r"(?:next|coming|upcoming)\s+(\d{1,2})\s+days?",
        raw,
    )
    if m:
        n = max(1, min(16, int(m.group(1))))
        return {"start": today, "end": today + timedelta(days=n - 1), "kind": "next_n"}

    if re.search(r"\b(this week|coming week|next week)\b", raw):
        end = today + timedelta(days=6)
        return {"start": today, "end": end, "kind": "next_n"}

    m = re.search(
        r"(\d{4}-\d{2}-\d{2})\s*(?:to|through|till|until|-)\s*(\d{4}-\d{2}-\d{2})",
        raw,
    )
    if m:
        a, b = date.fromisoformat(m.group(1)), date.fromisoformat(m.group(2))
        if b < a:
            a, b = b, a
        return {"start": a, "end": b, "kind": "range"}

    months = "|".join(sorted(_MONTHS, key=len, reverse=True))
    # 23 to 28th August / 23-28 August / 23rd–28 Aug 2026
    m = re.search(
        rf"(?:from\s+|between\s+)?{_ORD.pattern}\s*(?:to|through|till|until|-)\s*{_ORD.pattern}"
        rf"(?:\s+(?:of\s+)?)?(?P<mon>{months})(?:\s+(?P<year>\d{{4}}))?",
        raw,
    )
    if m:
        d1, d2 = int(m.group(1)), int(m.group(2))
        mon = _MONTHS[m.group("mon")]
        year = int(m.group("year") or _year_for(mon, d1, today))
        a, b = _mk(year, mon, d1), _mk(year, mon, d2)
        if a and b:
            if b < a:
                a, b = b, a
            return {"start": a, "end": b, "kind": "range"}

    # 23 August to 28 August
    m = re.search(
        rf"{_ORD.pattern}\s+(?P<m1>{months})(?:\s+(?P<y1>\d{{4}}))?\s*"
        rf"(?:to|through|till|until|-)\s*"
        rf"{_ORD.pattern}\s+(?P<m2>{months})(?:\s+(?P<y2>\d{{4}}))?",
        raw,
    )
    if m:
        mon1, mon2 = _MONTHS[m.group("m1")], _MONTHS[m.group("m2")]
        y1 = int(m.group("y1") or _year_for(mon1, int(m.group(1)), today))
        y2 = int(m.group("y2") or y1)
        a, b = _mk(y1, mon1, int(m.group(1))), _mk(y2, mon2, int(m.group(2)))
        if a and b:
            if b < a:
                a, b = b, a
            return {"start": a, "end": b, "kind": "range"}

    # single day: 25th August / 25 Aug 2026
    m = re.search(
        rf"(?:on\s+|for\s+)?{_ORD.pattern}\s+(?P<mon>{months})(?:\s+(?P<year>\d{{4}}))?",
        raw,
    )
    if m:
        day = int(m.group(1))
        mon = _MONTHS[m.group("mon")]
        year = int(m.group("year") or _year_for(mon, day, today))
        d = _mk(year, mon, day)
        if d:
            return {"start": d, "end": d, "kind": "day"}

    if re.search(r"\bthis weekend\b", raw):
        wd = today.weekday()
        if wd == 6:
            sat, sun = today - timedelta(days=1), today
        elif wd == 5:
            sat, sun = today, today + timedelta(days=1)
        else:
            sat = today + timedelta(days=(5 - wd))
            sun = sat + timedelta(days=1)
        return {"start": sat, "end": sun, "kind": "weekend"}

    if re.search(r"\btomorrow\b", raw):
        d = today + timedelta(days=1)
        return {"start": d, "end": d, "kind": "day"}

    if re.search(r"\b(today|tonight)\b", raw):
        return {"start": today, "end": today, "kind": "day"}

    return None


def iso_span(window: dict[str, Any] | None) -> tuple[str | None, str | None]:
    if not window:
        return None, None
    return window["start"].isoformat(), window["end"].isoformat()

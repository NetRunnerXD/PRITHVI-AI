"""S3: structured keep/change query after gazetteer + dates."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.schemas.location import Location


@dataclass
class ResolvedQuery:
    text_en: str
    location: Location
    time_range: dict[str, str] | None = None
    keep: list[str] = field(default_factory=list)
    change: list[str] = field(default_factory=list)
    persona: str = "household"
    persona_confidence: float = 0.4


_FARMER = ("pump", "field", "irrigat", "mandi", "kharif", "rabi", "paddy", "wheat", "crop")
_LABOUR = ("labour", "labor", "midday", "heat stroke", "wbgt", "outdoor work")


def infer_persona(text_en: str) -> tuple[str, float]:
    t = (text_en or "").lower()
    if any(w in t for w in _FARMER):
        return "farmer", 0.85
    if any(w in t for w in _LABOUR):
        return "labour", 0.8
    return "household", 0.4


def build(
    text_en: str,
    loc: Location,
    *,
    window: dict[str, str] | None,
    inherited_place: bool,
    new_place: bool,
) -> ResolvedQuery:
    persona, conf = infer_persona(text_en)
    keep: list[str] = []
    change: list[str] = []
    if inherited_place:
        keep.append("location")
    if new_place:
        change.append("location")
    if window:
        change.append("time")
    else:
        keep.append("time")
    keep.append("persona")
    return ResolvedQuery(
        text_en=text_en,
        location=loc,
        time_range=window,
        keep=keep,
        change=change,
        persona=persona,
        persona_confidence=conf,
    )


def as_dict(q: ResolvedQuery) -> dict[str, Any]:
    return {
        "text_en": q.text_en,
        "location": q.location.model_dump(),
        "time_range": q.time_range,
        "keep": q.keep,
        "change": q.change,
        "persona": q.persona,
        "persona_confidence": q.persona_confidence,
    }

"""In-process conversation state for follow-ups and regenerate."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.agents.dimensions import Dimensions


@dataclass
class TurnState:
    location: dict[str, Any] | None = None
    dimensions: Dimensions | None = None
    collected_keys: list[str] = field(default_factory=list)
    question_en: str = ""
    content_en: str = ""
    last_refuse: str | None = None
    asked: str | None = None
    catalog: bool = False


_STORE: dict[str, TurnState] = {}
_MAX = 40


def load(cid: str | None) -> TurnState | None:
    if not cid:
        return None
    return _STORE.get(cid)


def save(cid: str | None, state: TurnState) -> None:
    if not cid:
        return
    _STORE[cid] = state
    if len(_STORE) > _MAX:
        extra = list(_STORE.keys())[: len(_STORE) - _MAX]
        for k in extra:
            _STORE.pop(k, None)

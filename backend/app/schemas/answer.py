"""Grounded answer layout. The model chooses blocks; the binder fills numbers."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


TAB_IDS = (
    "overview",
    "nowcast",
    "alerts",
    "map",
    "forecast",
    "predicted",
    "risks",
    "market",
    "advisor",
    "settings",
)

BlockType = Literal[
    "prose",
    "metrics",
    "table",
    "decision",
    "compare",
    "timeline",
    "sources",
    "ui",
]


class MetricItem(BaseModel):
    label: str
    cite: str
    unit: str = ""
    value: Any = None


class AnswerBlock(BaseModel):
    type: str
    text: str | None = None
    title: str | None = None
    items: list[MetricItem] | list[dict[str, Any]] | None = None
    frm: str | None = Field(default=None, alias="from")
    columns: list[str] | None = None
    rows: list[Any] | None = None
    action: str | None = None
    when: str | None = None
    why: str | None = None
    tab: str | None = None
    highlight: str | None = None
    center: list[float] | None = None
    zoom: float | None = None
    cites: list[str] | None = None

    model_config = {"populate_by_name": True, "extra": "allow"}


class UiAction(BaseModel):
    op: str
    tab: str | None = None
    location: dict[str, Any] | None = None
    path: str | None = None
    value: Any = None
    target: str | None = None
    center: list[float] | None = None
    zoom: float | None = None
    highlight: str | None = None


class AnswerSpec(BaseModel):
    format: str = "free"
    title: str | None = None
    blocks: list[dict[str, Any]] = Field(default_factory=list)
    sources: list[str] = Field(default_factory=list)

    model_config = {"extra": "allow"}

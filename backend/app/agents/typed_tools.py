"""Typed chat tools on top of DataLib.

The model sees seven narrow functions with enums and formats instead of one generic
data(need=…). Each call is validated (pydantic) and mapped onto the existing DataLib
need, so the fact packs, claim checks and UI blocks stay exactly as before.
The legacy `data` name is still accepted when a model emits it.
"""

from __future__ import annotations

import json
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from app.agents.data_tool import NEEDS

_DATE = r"^\d{4}-\d{2}-\d{2}$"
RANK_METRICS = ("flood", "rain", "drought", "heat", "irrigation")


class _Args(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    @field_validator("*", mode="before")
    @classmethod
    def _blank_to_none(cls, v: Any) -> Any:
        return None if isinstance(v, str) and not v.strip() else v


class PlaceArgs(_Args):
    place: str | None = Field(None, max_length=80)


class ForecastArgs(PlaceArgs):
    start_date: str | None = Field(None, pattern=_DATE)
    end_date: str | None = Field(None, pattern=_DATE)
    hour: int | None = Field(None, ge=0, le=23)


class CompareArgs(_Args):
    place: str | None = Field(None, max_length=80)
    other: str = Field(..., min_length=2, max_length=80)


class RankArgs(_Args):
    state: str = Field(..., min_length=2, max_length=60)
    metric: Literal["flood", "rain", "drought", "heat", "irrigation"] = "flood"


class LegacyArgs(_Args):
    model_config = ConfigDict(extra="ignore", str_strip_whitespace=True)
    need: str
    place: str | None = None
    start: str | None = None
    end: str | None = None
    other: str | None = None
    state: str | None = None
    metric: str | None = None
    question: str | None = None
    hour: int | None = Field(None, ge=0, le=23)

    @field_validator("need")
    @classmethod
    def _need(cls, v: str) -> str:
        v = (v or "").strip().lower()
        if v not in NEEDS:
            raise ValueError(f"need must be one of {', '.join(NEEDS)}")
        return v


_PLACE_PROP = {"type": "string", "description": "Indian town, city or district. Omit for the user's pinned place."}


def _fn(name: str, desc: str, props: dict[str, Any], required: list[str] | None = None) -> dict[str, Any]:
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": desc,
            "parameters": {
                "type": "object",
                "properties": props,
                "required": required or [],
                "additionalProperties": False,
            },
        },
    }


TOOLS: list[dict[str, Any]] = [
    _fn(
        "get_forecast",
        "Current conditions and the 7-16 day forecast: temperature, sky, rain mm and probability. "
        "Give start_date/end_date for named days (rain totals for that window) and hour for a time of day.",
        {
            "place": _PLACE_PROP,
            "start_date": {"type": "string", "description": "YYYY-MM-DD (IST)"},
            "end_date": {"type": "string", "description": "YYYY-MM-DD (IST), same as start_date for one day"},
            "hour": {"type": "integer", "description": "IST clock hour 0-23 for a time-of-day question"},
        },
    ),
    _fn(
        "get_nowcast",
        "Next 0-6 hours (PRITHVI nowcast): will it rain soon, onset time, storm cells, 90-minute pump/field decision.",
        {"place": _PLACE_PROP},
    ),
    _fn(
        "get_alerts",
        "Official alerts in force: IMD/NDMA (Sachet) CAP warnings, thunderstorm, lightning, heat, flood, cyclone, "
        "earthquake and tsunami advisories.",
        {"place": _PLACE_PROP},
    ),
    _fn(
        "get_air_quality",
        "Air quality now: CPCB national AQI (nearest station), category and main pollutant.",
        {"place": _PLACE_PROP},
    ),
    _fn(
        "get_risks",
        "Risk scores at the place: flood/waterlogging, heat stress, drought, irrigation need, marine, seismic.",
        {"place": _PLACE_PROP},
    ),
    _fn(
        "compare_places",
        "Compare rain and flood risk between two Indian places.",
        {"place": _PLACE_PROP, "other": {"type": "string", "description": "Second Indian town or district"}},
        ["other"],
    ),
    _fn(
        "rank_districts",
        "Rank the districts of one Indian state by a risk metric.",
        {
            "state": {"type": "string", "description": "Indian state name"},
            "metric": {"type": "string", "enum": list(RANK_METRICS)},
        },
        ["state"],
    ),
]

TOOL_NAMES = tuple(t["function"]["name"] for t in TOOLS)

_MODELS: dict[str, type[_Args]] = {
    "get_forecast": ForecastArgs,
    "get_nowcast": PlaceArgs,
    "get_alerts": PlaceArgs,
    "get_air_quality": PlaceArgs,
    "get_risks": PlaceArgs,
    "compare_places": CompareArgs,
    "rank_districts": RankArgs,
    "data": LegacyArgs,
}

_NEED_OF = {
    "get_nowcast": "nowcast",
    "get_alerts": "warnings",
    "get_air_quality": "aqi",
    "get_risks": "risks",
    "compare_places": "compare",
    "rank_districts": "rank",
}

# need → typed tool (for traces and the eval)
TOOL_OF_NEED = {
    "forecast": "get_forecast",
    "rain_window": "get_forecast",
    "nowcast": "get_nowcast",
    "warnings": "get_alerts",
    "aqi": "get_air_quality",
    "risks": "get_risks",
    "compare": "compare_places",
    "rank": "rank_districts",
}


def _raw_args(raw: Any) -> dict[str, Any] | None:
    if isinstance(raw, dict):
        return raw
    if raw in (None, ""):
        return {}
    try:
        data = json.loads(raw)
    except (TypeError, ValueError):
        return None
    return data if isinstance(data, dict) else None


def to_data_args(name: str, raw: Any) -> tuple[dict[str, Any] | None, str | None]:
    """Validate one tool call. Returns (DataLib args, None) or (None, error for the model)."""
    model = _MODELS.get(name or "")
    if model is None:
        return None, f"unknown function {name!r}; use one of: {', '.join(TOOL_NAMES)}"
    args = _raw_args(raw)
    if args is None:
        return None, "arguments must be a JSON object"
    try:
        v = model.model_validate(args)
    except ValidationError as exc:
        bits = []
        for e in exc.errors()[:4]:
            loc = ".".join(str(x) for x in e.get("loc") or ()) or "args"
            bits.append(f"{loc}: {e.get('msg')}")
        return None, "invalid arguments: " + "; ".join(bits)
    d = v.model_dump(exclude_none=True)
    if name == "data":
        return d, None
    if name == "get_forecast":
        out: dict[str, Any] = {"need": "forecast"}
        if d.get("place"):
            out["place"] = d["place"]
        a, b = d.get("start_date"), d.get("end_date")
        if a and b and b < a:
            return None, "invalid arguments: end_date is before start_date"
        if a and "hour" not in d:
            out.update(need="rain_window", start=a, end=b or a)
        elif a:
            out.update(start=a, end=b or a)
        if "hour" in d:
            out["hour"] = d["hour"]
        return out, None
    out = {"need": _NEED_OF[name], **d}
    return out, None

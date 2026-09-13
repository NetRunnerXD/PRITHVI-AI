"""UTC-only timestamps for storage and filters.

ISO strings are always `YYYY-MM-DDTHH:MM:SSZ`. Horizon filters use millisecond
integers. Naive Open-Meteo times are UTC (fetch with timezone=UTC).
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

ALLOWED_H = (1, 3, 6, 12)
KEEP_H = 12
KEEP_MS = KEEP_H * 3600 * 1000


def to_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def iso_z(dt: datetime) -> str:
    return to_utc(dt).strftime("%Y-%m-%dT%H:%M:%SZ")


def ms(dt: datetime) -> int:
    return int(to_utc(dt).timestamp() * 1000)


def from_ms(value: int | float) -> datetime:
    v = float(value)
    if v < 1e12:
        v *= 1000.0
    return datetime.fromtimestamp(v / 1000.0, tz=timezone.utc)


def parse_any(raw: Any, *, naive_utc: bool = True) -> datetime | None:
    if raw is None or raw == "":
        return None
    if isinstance(raw, datetime):
        return to_utc(raw)
    if isinstance(raw, (int, float)) and raw == raw:
        try:
            return from_ms(raw)
        except (OverflowError, OSError, ValueError):
            return None
    s = str(raw).strip()
    if not s:
        return None
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    try:
        t = datetime.fromisoformat(s[:32])
    except ValueError:
        return None
    if t.tzinfo is None:
        t = t.replace(tzinfo=timezone.utc if naive_utc else timezone.utc)
    return to_utc(t)


def clamp_horizon(past_h: Any, default: int = 6) -> int:
    try:
        h = int(float(past_h))
    except (TypeError, ValueError):
        return default
    return h if h in ALLOWED_H else default


def now_utc() -> datetime:
    return datetime.now(timezone.utc)

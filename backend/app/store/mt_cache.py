"""Persistent translation cache on the satellite/event cluster (MONGODB_SAT_URI).

Small docs ({_id: key, text, src, engine, expire_at}), 30-day TTL. The in-process LRU in
app.cache sits in front; this layer only matters after a restart or spin-down.
Reads are bounded by a short timeout and every failure disables the layer for a while,
so a slow or missing cluster never slows a chat turn.
"""

from __future__ import annotations

import asyncio
import time
from datetime import datetime, timedelta, timezone
from typing import Any

from app.store import sat_mongo

COL = "mt_cache"
TTL_DAYS = 30
READ_TIMEOUT_S = 0.8
_COOLDOWN_S = 300.0
_down_until = 0.0
_indexed = False


def _col():
    global _indexed
    c = sat_mongo.col(COL)
    if c is not None and not _indexed:
        try:
            c.create_index("expire_at", expireAfterSeconds=0)
        except Exception:  # noqa: BLE001
            pass
        _indexed = True
    return c


def _usable() -> bool:
    return sat_mongo.sat_mongo_ok() and time.monotonic() >= _down_until


def _trip() -> None:
    global _down_until
    _down_until = time.monotonic() + _COOLDOWN_S


def _get_sync(key: str) -> dict[str, Any] | None:
    c = _col()
    if c is None:
        return None
    doc = c.find_one({"_id": key}, {"_id": 0, "text": 1, "src": 1, "engine": 1})
    return doc or None


def _set_sync(key: str, value: dict[str, Any]) -> None:
    c = _col()
    if c is None:
        return
    doc = {
        "text": str(value.get("text") or "")[:8000],
        "src": value.get("src"),
        "engine": value.get("engine"),
        "expire_at": datetime.now(timezone.utc) + timedelta(days=TTL_DAYS),
    }
    c.update_one({"_id": key}, {"$set": doc}, upsert=True)


async def get(key: str) -> dict[str, Any] | None:
    if not _usable():
        return None
    try:
        return await asyncio.wait_for(asyncio.to_thread(_get_sync, key), READ_TIMEOUT_S)
    except Exception:  # noqa: BLE001
        _trip()
        return None


def put(key: str, value: dict[str, Any]) -> None:
    """Fire-and-forget write."""
    if not _usable() or not (value.get("text") or "").strip():
        return

    async def _w() -> None:
        try:
            await asyncio.wait_for(asyncio.to_thread(_set_sync, key, value), 5.0)
        except Exception:  # noqa: BLE001
            _trip()

    try:
        asyncio.get_running_loop().create_task(_w())
    except RuntimeError:
        pass

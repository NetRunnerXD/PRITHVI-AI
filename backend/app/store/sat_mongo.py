"""Sync client for the satellite/event cluster (MONGODB_SAT_URI)."""

from __future__ import annotations

import os
import threading
from typing import Any

from app.config import get_settings

_client = None
_lock = threading.Lock()
_indexed = False


def sat_mongo_ok() -> bool:
    if os.environ.get("PYTEST_CURRENT_TEST"):
        return False
    s = get_settings()
    return bool((s.mongodb_sat_uri or s.mongodb_uri or "").strip())


def _uri() -> str:
    s = get_settings()
    return (s.mongodb_sat_uri or s.mongodb_uri or "").strip()


def db_name() -> str:
    s = get_settings()
    return (s.mongodb_sat_db or "rituchakra_sat").strip() or "rituchakra_sat"


def client():
    global _client
    if not sat_mongo_ok():
        return None
    with _lock:
        if _client is None:
            from pymongo import MongoClient

            _client = MongoClient(_uri(), serverSelectionTimeoutMS=8000)
        return _client


def db():
    c = client()
    if c is None:
        return None
    return c[db_name()]


def col(name: str):
    database = db()
    if database is None:
        return None
    _ensure_indexes(database)
    return database[name]


def _ensure_indexes(database) -> None:
    global _indexed
    if _indexed:
        return
    try:
        ev = database["hazard_events"]
        ev.create_index("event_id", unique=True)
        ev.create_index([("kind", 1), ("phase", 1), ("started_ms", 1)])
        ev.create_index([("state", 1), ("started_ms", 1)])
        ev.create_index([("track_id", 1), ("phase", 1)])
        ev.create_index("expire_at", expireAfterSeconds=0)
        frames = database["sat_frames"]
        frames.create_index("frame_id", unique=True)
        frames.create_index("granule_id")
        frames.create_index("started_ms")
        database["ir_frames"].create_index("t")
        database["mosdac_quota"].create_index("day_ist", unique=True)
        database["alert_windows"].create_index("started_ms")
        _indexed = True
    except Exception:
        pass


def wipe_user_databases() -> dict[str, Any]:
    """Clear every user collection on the sat cluster. Requires sat_wipe_confirm.

    Atlas custom users often cannot dropDatabase; we drop/empty collections instead.
    """
    s = get_settings()
    if not s.sat_wipe_confirm:
        return {"ok": False, "status": "sat_wipe_confirm_off"}
    c = client()
    if c is None:
        return {"ok": False, "status": "no_client"}
    keep = {"admin", "local", "config"}
    cleared: list[str] = []
    errors: list[str] = []
    for name in list(c.list_database_names()):
        if name in keep:
            continue
        database = c[name]
        try:
            c.drop_database(name)
            cleared.append(name + " (dropped db)")
            continue
        except Exception:
            pass
        try:
            for coll_name in list(database.list_collection_names()):
                try:
                    database.drop_collection(coll_name)
                    cleared.append(f"{name}.{coll_name}")
                except Exception:
                    try:
                        n = database[coll_name].delete_many({}).deleted_count
                        cleared.append(f"{name}.{coll_name} ({n} docs)")
                    except Exception as e:
                        errors.append(f"{name}.{coll_name}: {e}")
        except Exception as e:
            errors.append(f"{name}: {e}")
    global _indexed
    _indexed = False
    database = c[db_name()]
    _ensure_indexes(database)
    return {"ok": not errors, "cleared": cleared, "errors": errors, "db": db_name()}

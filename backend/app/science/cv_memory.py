"""Optional convective memory: disk first, Mongo write-behind.

Does not replace INSAT fetch, does not skip JPEG, does not write millimetres,
does not gate alerts. Empty MONGODB_URI = disk JSON only. Request path never
waits on Atlas.
"""

from __future__ import annotations

import json
import os
import threading
from datetime import datetime, timedelta, timezone
from typing import Any

from app.config import ROOT, get_settings

DISK = ROOT / ".cache" / "cv_memory.json"
KEEP_H = 12.0
_client = None
_lock = threading.Lock()


def mongo_ok() -> bool:
    if os.environ.get("PYTEST_CURRENT_TEST"):
        return False
    return bool((get_settings().mongodb_uri or "").strip())


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _col(name: str):
    global _client
    if not mongo_ok():
        return None
    if _client is None:
        from pymongo import MongoClient

        _client = MongoClient(get_settings().mongodb_uri.strip(), serverSelectionTimeoutMS=2500)
        db = _client[get_settings().mongodb_db or "rituchakra"]
        try:
            db.storm_cells.create_index("id", unique=True)
            db.storm_cells.create_index("last_seen")
            db.ir_frames.create_index("t")
        except Exception:
            pass
    return _client[get_settings().mongodb_db or "rituchakra"][name]


def _slim_cell(c: dict[str, Any]) -> dict[str, Any] | None:
    try:
        lat, lon = float(c["lat"]), float(c["lon"])
    except (KeyError, TypeError, ValueError):
        return None
    cid = str(c.get("event_id") or c.get("id") or f"{round(lat, 3)}:{round(lon, 3)}:{c.get('kind') or 'storm'}:{c.get('first_seen') or c.get('started_ms') or c.get('t') or _now()}")
    t = c.get("last_seen") or c.get("first_seen") or c.get("t") or _now()
    return {
        "id": cid,
        "event_id": cid,
        "lat": lat,
        "lon": lon,
        "kind": c.get("kind") or "storm",
        "place": c.get("place"),
        "min_tb_k": c.get("min_tb_k"),
        "area_km2": c.get("area_km2"),
        "rain_ir_mm_h": c.get("rain_ir_mm_h"),
        "p_lightning": c.get("p_lightning"),
        "p_cloudburst": c.get("p_cloudburst"),
        "ot": c.get("ot"),
        "trend": c.get("trend"),
        "first_seen": c.get("first_seen") or t,
        "last_seen": t,
        "t": t,
        "phase": c.get("phase") or "live",
    }


def _disk_load() -> dict[str, Any]:
    if not DISK.exists():
        return {"cells": [], "frames": []}
    try:
        blob = json.loads(DISK.read_text(encoding="utf-8"))
        return blob if isinstance(blob, dict) else {"cells": [], "frames": []}
    except (OSError, json.JSONDecodeError):
        return {"cells": [], "frames": []}


def _disk_save(blob: dict[str, Any]) -> None:
    try:
        DISK.parent.mkdir(parents=True, exist_ok=True)
        DISK.write_text(json.dumps(blob, ensure_ascii=False), encoding="utf-8")
    except OSError:
        pass


def _merge_cells(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    cutoff = datetime.now(timezone.utc) - timedelta(hours=KEEP_H)
    by_id: dict[str, dict[str, Any]] = {}
    for c in rows:
        slim = _slim_cell(c) if "id" in c or "lat" in c else None
        if not slim:
            continue
        last = slim.get("last_seen")
        try:
            ts = datetime.fromisoformat(str(last).replace("Z", "+00:00"))
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)
            if ts < cutoff:
                continue
        except ValueError:
            pass
        prev = by_id.get(slim["id"])
        if prev and prev.get("first_seen"):
            slim["first_seen"] = prev["first_seen"]
        by_id[slim["id"]] = slim
    return list(by_id.values())[-400:]


def _write_cells(rows: list[dict[str, Any]]) -> None:
    slim = [s for s in (_slim_cell(c) for c in rows) if s]
    if not slim:
        return
    with _lock:
        blob = _disk_load()
        blob["cells"] = _merge_cells(list(blob.get("cells") or []) + slim)
        blob["t"] = _now()
        _disk_save(blob)
    col = _col("storm_cells")
    if col is None:
        return
    try:
        from pymongo import UpdateOne

        ops = [UpdateOne({"id": s["id"]}, {"$set": s}, upsert=True) for s in slim]
        if ops:
            col.bulk_write(ops, ordered=False)
    except Exception:
        pass


def _write_frame(cells: list[dict[str, Any]], t: str | None = None) -> None:
    t = t or _now()
    slim = [s for s in (_slim_cell(c) for c in cells) if s]
    frame = {"t": t, "n": len(slim), "cells": slim[:120]}
    with _lock:
        blob = _disk_load()
        frames = list(blob.get("frames") or [])
        frames.append(frame)
        blob["frames"] = frames[-3:]
        blob["t"] = t
        _disk_save(blob)
    col = _col("ir_frames")
    if col is None:
        return
    try:
        col.insert_one({"_id": t, **frame})
        old = list(col.find({}, {"_id": 1, "t": 1}).sort("t", -1).skip(3))
        if old:
            col.delete_many({"_id": {"$in": [d["_id"] for d in old]}})
    except Exception:
        pass


def remember_cells(rows: list[dict[str, Any]]) -> None:
    if os.environ.get("PYTEST_CURRENT_TEST") or not rows:
        return
    threading.Thread(target=_write_cells, args=(list(rows),), daemon=True).start()


def remember_frame(cells: list[dict[str, Any]], t: str | None = None) -> None:
    if os.environ.get("PYTEST_CURRENT_TEST"):
        return
    threading.Thread(target=_write_frame, args=(list(cells), t), daemon=True).start()


def last_ir_cells() -> list[dict[str, Any]]:
    """Previous IR cells for tracking only — never a substitute for a live JPEG."""
    with _lock:
        frames = list(_disk_load().get("frames") or [])
    if frames:
        return list((frames[-1] or {}).get("cells") or [])
    col = _col("ir_frames")
    if col is None:
        return []
    try:
        doc = col.find_one(sort=[("t", -1)])
        return list((doc or {}).get("cells") or [])
    except Exception:
        return []


def past_cells(now: datetime | None = None, hours: float = KEEP_H) -> list[dict[str, Any]]:
    now = now or datetime.now(timezone.utc)
    cutoff = now - timedelta(hours=hours)
    rows: list[dict[str, Any]] = []
    with _lock:
        rows.extend(_disk_load().get("cells") or [])
    col = _col("storm_cells")
    if col is not None:
        try:
            rows.extend(list(col.find({}, {"_id": 0}).limit(400)))
        except Exception:
            pass
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for c in rows:
        slim = _slim_cell(c)
        if not slim or slim["id"] in seen:
            continue
        last = slim.get("last_seen") or slim.get("t")
        try:
            ts = datetime.fromisoformat(str(last).replace("Z", "+00:00"))
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)
            if ts < cutoff:
                continue
        except ValueError:
            continue
        seen.add(slim["id"])
        out.append(slim)
    return out

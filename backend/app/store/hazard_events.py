"""One Mongo document per hazard occurrence. Never upsert by lat/lon."""

from __future__ import annotations

import os
import threading
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from app.store import sat_mongo
from app.store.time import KEEP_H, KEEP_MS, clamp_horizon, iso_z, ms, now_utc, parse_any, to_utc

_disk_lock = threading.Lock()
_DISK_EVENTS: list[dict[str, Any]] = []

LIVE_GAP_MS = 20 * 60 * 1000


def _new_id() -> str:
    return uuid.uuid4().hex


_NAMED = {
    "cloud",
    "cloudburst",
    "downburst",
    "fire",
    "landslide",
    "lightning",
    "storm",
}


def slim_event(row: dict[str, Any]) -> dict[str, Any] | None:
    try:
        lat, lon = float(row["lat"]), float(row["lon"])
    except (KeyError, TypeError, ValueError):
        return None
    kind = str(row.get("kind") or "").strip()
    if kind not in _NAMED:
        return None
    place = str(row.get("place") or row.get("title") or row.get("label") or "").strip()
    if not place:
        try:
            from app.data.india_districts import nearest

            d = nearest(lat, lon) or {}
            place = str(d.get("label") or "").strip()
            if not place and d.get("district"):
                place = f"{d.get('district')}, {d.get('state') or ''}".strip(", ")
        except Exception:
            place = ""
    if not place:
        return None
    started = parse_any(row.get("started_at") or row.get("started_ms") or row.get("t"))
    closes = parse_any(row.get("closes_at") or row.get("closes_ms"))
    occurred = parse_any(row.get("occurred_at") or row.get("occurred_ms"))
    now = now_utc()
    if started is None:
        started = now
    if closes is None:
        closes = started + timedelta(minutes=20)
    started_ms = int(row.get("started_ms") or ms(started))
    closes_ms = int(row.get("closes_ms") or ms(closes))
    occurred_ms = int(row["occurred_ms"]) if row.get("occurred_ms") is not None else (ms(occurred) if occurred else None)
    event_id = str(row.get("event_id") or row.get("id") or _new_id())
    phase = str(row.get("phase") or "live")
    expire = datetime.fromtimestamp((max(closes_ms, started_ms, occurred_ms or 0) + KEEP_MS) / 1000.0, tz=timezone.utc)
    out = {
        "event_id": event_id,
        "track_id": row.get("track_id") or row.get("parent") or row.get("id"),
        "kind": kind,
        "phase": phase,
        "lat": lat,
        "lon": lon,
        "place": place,
        "state": row.get("state"),
        "started_at": iso_z(started),
        "started_ms": started_ms,
        "closes_at": iso_z(closes),
        "closes_ms": closes_ms,
        "occurred_at": iso_z(occurred) if occurred else None,
        "occurred_ms": occurred_ms,
        "parent_event_id": row.get("parent_event_id") or row.get("parent"),
        "lead_min": row.get("lead_min"),
        "engine": row.get("engine"),
        "p_lightning": row.get("p_lightning"),
        "p_cloudburst": row.get("p_cloudburst"),
        "confidence": row.get("confidence"),
        "confidence_band": row.get("confidence_band"),
        "verify": row.get("verify"),
        "gate": row.get("gate"),
        "sources": row.get("sources"),
        "ingest_cycle_id": row.get("ingest_cycle_id"),
        "expire_at": expire,
        "rain_ir_mm_h": row.get("rain_ir_mm_h"),
        "min_tb_k": row.get("min_tb_k"),
        "area_km2": row.get("area_km2"),
        "n": row.get("n"),
        "frp_mw": row.get("frp_mw"),
        "note": row.get("note"),
        "id": event_id,
    }
    return out


def _keep(row: dict[str, Any], now: datetime) -> bool:
    last = row.get("closes_ms") or row.get("occurred_ms") or row.get("started_ms")
    if last is None:
        return True
    return int(last) >= ms(now) - KEEP_MS


def upsert_many(rows: list[dict[str, Any]]) -> int:
    if os.environ.get("PYTEST_CURRENT_TEST") or not rows:
        return 0
    now = now_utc()
    slim = [s for s in (slim_event(r) for r in rows) if s and _keep(s, now)]
    if not slim:
        return 0
    with _disk_lock:
        by_id = {e["event_id"]: e for e in _DISK_EVENTS if _keep(e, now)}
        for s in slim:
            by_id[s["event_id"]] = s
        _DISK_EVENTS.clear()
        _DISK_EVENTS.extend(by_id.values())
    col = sat_mongo.col("hazard_events")
    if col is None:
        return len(slim)
    try:
        from pymongo import UpdateOne

        ops = []
        for s in slim:
            doc = {k: v for k, v in s.items() if k != "_id"}
            ops.append(UpdateOne({"event_id": s["event_id"]}, {"$set": doc}, upsert=True))
        if ops:
            col.bulk_write(ops, ordered=False)
    except Exception:
        pass
    return len(slim)


def persist_live_cell(cell: dict[str, Any], now: datetime | None = None) -> dict[str, Any] | None:
    """Update the open live event for track_id, or insert a new occurrence."""
    now = now or now_utc()
    slim = slim_event({**cell, "phase": cell.get("phase") or "live"})
    if not slim:
        return None
    track = str(slim.get("track_id") or "")
    col = sat_mongo.col("hazard_events")
    existing = None
    if track and col is not None:
        try:
            existing = col.find_one(
                {"track_id": track, "phase": "live", "kind": slim["kind"]},
                {"_id": 0},
            )
        except Exception:
            existing = None
    if existing and int(existing.get("closes_ms") or 0) >= slim["started_ms"] - LIVE_GAP_MS:
        slim["event_id"] = existing["event_id"]
        slim["id"] = existing["event_id"]
        slim["started_ms"] = int(existing.get("started_ms") or slim["started_ms"])
        slim["started_at"] = existing.get("started_at") or slim["started_at"]
    elif existing:
        close_track(track, now, kind=slim["kind"])
        slim["event_id"] = _new_id()
        slim["id"] = slim["event_id"]
    upsert_many([slim])
    return slim


def close_track(track_id: str, now: datetime, *, kind: str | None = None) -> None:
    now_ms = ms(now)
    col = sat_mongo.col("hazard_events")
    q: dict[str, Any] = {"track_id": track_id, "phase": "live"}
    if kind:
        q["kind"] = kind
    patch = {
        "phase": "past",
        "closes_ms": now_ms,
        "closes_at": iso_z(now),
        "occurred_ms": now_ms,
        "occurred_at": iso_z(now),
    }
    if col is not None:
        try:
            col.update_many(q, {"$set": patch})
        except Exception:
            pass
    with _disk_lock:
        for e in _DISK_EVENTS:
            if e.get("track_id") == track_id and e.get("phase") == "live":
                if kind and e.get("kind") != kind:
                    continue
                e.update(patch)


def prune(now: datetime | None = None) -> int:
    now = now or now_utc()
    cutoff = ms(now) - KEEP_MS
    n = 0
    col = sat_mongo.col("hazard_events")
    if col is not None:
        try:
            res = col.delete_many(
                {
                    "$expr": {
                        "$lt": [
                            {"$max": ["$closes_ms", "$occurred_ms", "$started_ms"]},
                            cutoff,
                        ]
                    }
                }
            )
            n = int(res.deleted_count or 0)
        except Exception:
            try:
                old = list(col.find({}, {"_id": 1, "closes_ms": 1, "occurred_ms": 1, "started_ms": 1}))
                ids = []
                for d in old:
                    last = max(int(d.get("closes_ms") or 0), int(d.get("occurred_ms") or 0), int(d.get("started_ms") or 0))
                    if last < cutoff:
                        ids.append(d["_id"])
                if ids:
                    col.delete_many({"_id": {"$in": ids}})
                    n = len(ids)
            except Exception:
                pass
    with _disk_lock:
        keep = [e for e in _DISK_EVENTS if _keep(e, now)]
        n += len(_DISK_EVENTS) - len(keep)
        _DISK_EVENTS[:] = keep
    return n


def query(*, past_h: int = 6, kinds: list[str] | None = None, now: datetime | None = None) -> list[dict[str, Any]]:
    now = now or now_utc()
    h = clamp_horizon(past_h)
    now_ms = ms(now)
    past_cut = now_ms - h * 3600_000
    fwd_cut = now_ms + h * 3600_000
    rows: list[dict[str, Any]] = []
    with _disk_lock:
        rows.extend(list(_DISK_EVENTS))
    col = sat_mongo.col("hazard_events")
    if col is not None:
        try:
            rows.extend(list(col.find({}, {"_id": 0}).limit(2000)))
        except Exception:
            pass
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for r in rows:
        slim = slim_event(r)
        if not slim:
            continue
        eid = slim["event_id"]
        if eid in seen:
            continue
        if kinds and slim["kind"] not in kinds:
            continue
        phase = slim["phase"]
        if phase == "past":
            stamp = slim.get("occurred_ms") or slim.get("started_ms") or 0
            if int(stamp) < past_cut:
                continue
        elif phase == "predicted":
            if int(slim["started_ms"]) > fwd_cut or int(slim["closes_ms"]) < now_ms:
                continue
        else:
            if int(slim["closes_ms"]) < now_ms - 30_000:
                continue
        seen.add(eid)
        out.append(slim)
    return out


def persist_pack_incidents(pack: dict[str, Any], *, cycle_id: str | None = None) -> int:
    rows: list[dict[str, Any]] = []
    state = pack.get("state")
    for key in ("incidents", "predicted", "predicted_storms", "predicted_unverified", "cells", "past_cells", "strokes", "past_strokes", "fires", "landslides"):
        for raw in pack.get(key) or []:
            if not isinstance(raw, dict):
                continue
            row = {**raw, "state": raw.get("state") or state, "ingest_cycle_id": cycle_id}
            if not row.get("event_id"):
                sig = f"{row.get('id') or ''}:{row.get('kind')}:{row.get('started_ms') or row.get('occurred_ms') or ''}:{round(float(row.get('lat') or 0), 3)}:{round(float(row.get('lon') or 0), 3)}"
                row["event_id"] = uuid.uuid5(uuid.NAMESPACE_URL, sig).hex if any(sig.split(":")) else _new_id()
            rows.append(row)
    n = upsert_many(rows)
    prune()
    return n

"""Singleton ingest_status for analyzing / ready banners."""

from __future__ import annotations

import json
import os
import threading
import uuid
from typing import Any

from app.store import sat_mongo
from app.store.time import iso_z, ms, now_utc

_lock = threading.Lock()
_MEM: dict[str, Any] = {
    "cycle_id": None,
    "phase": "idle",
    "ready": True,
    "message": "",
    "satellites": [],
    "started_ms": None,
    "updated_ms": None,
}

DOC_ID = "ingest_status"


def snapshot() -> dict[str, Any]:
    now = now_utc()
    blob = dict(_MEM)
    col = sat_mongo.col("ingest_status")
    if col is not None and not os.environ.get("PYTEST_CURRENT_TEST"):
        try:
            doc = col.find_one({"_id": DOC_ID}, {"_id": 0})
            if doc:
                blob.update(doc)
        except Exception:
            pass
    started = blob.get("started_ms")
    age_s = None
    if started:
        age_s = max(0.0, (ms(now) - int(started)) / 1000.0)
    sats = list(blob.get("satellites") or [])
    names = [s.get("name") or s.get("id") for s in sats if s.get("status") in {None, "pending", "fetching"}]
    if not names:
        names = [s.get("name") or s.get("id") for s in sats if s.get("status") == "ok"]
    ready = bool(blob.get("ready"))
    msg = blob.get("message") or ""
    phase = blob.get("phase") or "idle"
    # Honest readiness: a cycle that finished days ago is not "ready" data.
    stale_after = float(os.environ.get("INGEST_STALE_S") or 7200)
    stale = bool(age_s is not None and age_s > stale_after and phase not in {"fetching", "cv", "predict", "alerts"})
    if stale:
        ready = False
        phase = "stale"
        hrs = age_s / 3600.0
        msg = f"Satellite ingest is stale: last cycle {hrs:.0f} h ago. Map layers may be out of date."
    if not ready and not msg:
        label = ", ".join(str(n) for n in names if n) or "satellite"
        msg = f"Analyzing {label} data"
    return {
        "cycle_id": blob.get("cycle_id"),
        "phase": phase,
        "ready": ready,
        "stale": stale,
        "message": msg,
        "satellites": sats,
        "started_ms": blob.get("started_ms"),
        "updated_ms": blob.get("updated_ms"),
        "finished_at": blob.get("finished_at") or _slot_downloaded_at(),
        "data_time": blob.get("data_time") or _slot_data_time(),
        "age_s": age_s,
        "as_of": iso_z(now),
    }


def begin(satellites: list[dict[str, Any]]) -> str:
    now = now_utc()
    cid = uuid.uuid4().hex[:12]
    names = [s.get("name") or s.get("id") for s in satellites]
    label = ", ".join(str(n) for n in names if n)
    doc = {
        "cycle_id": cid,
        "phase": "fetching",
        "ready": False,
        "message": f"Analyzing {label} data" if label else "Analyzing satellite data",
        "satellites": [{**s, "status": s.get("status") or "pending"} for s in satellites],
        "started_ms": ms(now),
        "updated_ms": ms(now),
        "started_at": iso_z(now),
        "finished_at": _MEM.get("finished_at"),
    }
    _write(doc)
    return cid


def update(*, phase: str | None = None, satellite: dict[str, Any] | None = None, message: str | None = None) -> None:
    now = now_utc()
    with _lock:
        blob = dict(_MEM)
    if phase:
        blob["phase"] = phase
        if phase in {"ready", "error"}:
            blob["ready"] = phase == "ready"
    if message:
        blob["message"] = message
    if satellite and satellite.get("id"):
        sats = list(blob.get("satellites") or [])
        found = False
        for i, s in enumerate(sats):
            if s.get("id") == satellite["id"]:
                sats[i] = {**s, **satellite}
                found = True
                break
        if not found:
            sats.append(satellite)
        blob["satellites"] = sats
        pending = [s.get("name") or s.get("id") for s in sats if s.get("status") in {"pending", "fetching"}]
        if pending and not blob.get("ready"):
            blob["message"] = f"Analyzing {', '.join(str(n) for n in pending if n)} data"
    blob["updated_ms"] = ms(now)
    _write(blob)


def finish(*, ok: bool = True, message: str | None = None) -> None:
    now = now_utc()
    with _lock:
        blob = dict(_MEM)
    blob["phase"] = "ready" if ok else "error"
    blob["ready"] = ok
    blob["updated_ms"] = ms(now)
    if message:
        blob["message"] = message
    elif ok:
        blob["message"] = ""
    if ok:
        blob["finished_at"] = iso_z(now)
    _write(blob)


def _slot_data_time() -> str | None:
    """Latest product observation time saved in a slot file. Independent of this process's cycle."""
    best = ""
    for blob in _slot_blobs():
        products = blob.get("products") if isinstance(blob.get("products"), dict) else {}
        for raw in products.values():
            text = str(raw or "")
            if text > best:
                best = text
    return best or None


def _slot_downloaded_at() -> str | None:
    """Newest IST slot file, so a restart still shows the last successful download."""
    newest = None
    newest_at = ""
    for blob in _slot_blobs():
        at = str(blob.get("downloaded_at") or "")
        if at >= newest_at:
            newest_at = at
            newest = at or None
    return newest


def _slot_blobs() -> list[dict[str, Any]]:
    try:
        from app.ingest.worker import slot_dir
    except Exception:
        return []
    root = slot_dir()
    if root is None or not root.is_dir():
        return []
    out: list[dict[str, Any]] = []
    for p in root.glob("*.json"):
        try:
            blob = json.loads(p.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if isinstance(blob, dict):
            out.append(blob)
    return out


def _write(doc: dict[str, Any]) -> None:
    with _lock:
        _MEM.clear()
        _MEM.update(doc)
    col = sat_mongo.col("ingest_status")
    if col is None or os.environ.get("PYTEST_CURRENT_TEST"):
        return
    try:
        col.update_one({"_id": DOC_ID}, {"$set": {k: v for k, v in doc.items() if k != "_id"}}, upsert=True)
    except Exception:
        pass

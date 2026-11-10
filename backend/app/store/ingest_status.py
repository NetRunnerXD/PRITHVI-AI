"""Singleton ingest_status for analyzing / ready banners."""

from __future__ import annotations

import json
import os
import queue
import threading
import time
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

_view_lock = threading.Lock()
_mongo_view: dict[str, Any] = {}
_mongo_view_at = 0.0
_MONGO_VIEW_TTL_S = 5.0
_persist_q: queue.SimpleQueue = queue.SimpleQueue()
_writer_thread: threading.Thread | None = None
_FLUSH = object()


def empty_snapshot(now=None) -> dict[str, Any]:
    """Stable ingest shape used when no cycle is recorded or snapshot construction fails."""
    now = now or now_utc()
    return {
        "cycle_id": None,
        "phase": "idle",
        "ready": True,
        "stale": False,
        "message": "",
        "satellites": [],
        "started_ms": None,
        "updated_ms": None,
        "finished_at": None,
        "data_time": None,
        "age_s": None,
        "as_of": iso_z(now),
    }


def _coerce_satellites(raw: Any) -> list[dict[str, Any]]:
    if not isinstance(raw, list):
        return []
    return [s for s in raw if isinstance(s, dict)]


def _overlay_mongo() -> bool:
    """False under pytest unless a test patches this."""
    return not bool(os.environ.get("PYTEST_CURRENT_TEST"))


def snapshot() -> dict[str, Any]:
    try:
        return _snapshot()
    except Exception:
        return empty_snapshot()


def _snapshot() -> dict[str, Any]:
    now = now_utc()
    blob = dict(_MEM)
    if _overlay_mongo():
        doc = _mongo_status_doc()
        if isinstance(doc, dict):
            # A stale/idle Mongo doc must not hide a newer in-process cycle.
            # The API (separate process) still wins when Mongo is fresher.
            if _ms(doc.get("updated_ms")) >= _ms(blob.get("updated_ms")):
                blob.update(doc)
    started = blob.get("started_ms")
    age_s = None
    if started:
        try:
            age_s = max(0.0, (ms(now) - int(started)) / 1000.0)
        except (TypeError, ValueError):
            age_s = None
    sats = _coerce_satellites(blob.get("satellites"))
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


def finish(*, ok: bool = True, message: str | None = None, data_time: str | None = None) -> None:
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
    if data_time:
        blob["data_time"] = data_time
    _write(blob)
    print(
        f"ingest_status finish cycle_id={blob.get('cycle_id')} phase={blob.get('phase')} "
        f"data_time={blob.get('data_time') or blob.get('finished_at')}",
        flush=True,
    )
    return blob


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


def _ms(raw) -> int:
    try:
        return int(raw or 0)
    except (TypeError, ValueError):
        return 0


def _should_persist() -> bool:
    if os.environ.get("INGEST_STATUS_PERSIST_TEST"):
        return True
    if os.environ.get("PYTEST_CURRENT_TEST"):
        return False
    return True


def _on_event_loop() -> bool:
    try:
        import asyncio

        asyncio.get_running_loop()
        return True
    except RuntimeError:
        return False


def _cache_doc(doc: dict[str, Any]) -> None:
    global _mongo_view_at
    with _view_lock:
        _mongo_view.clear()
        _mongo_view.update(doc)
        _mongo_view_at = time.time()


def cached_mongo_doc(*, max_age_s: float | None = _MONGO_VIEW_TTL_S) -> dict[str, Any] | None:
    with _view_lock:
        if not _mongo_view:
            return None
        if max_age_s is not None and (time.time() - _mongo_view_at) > max_age_s:
            return None
        return dict(_mongo_view)


def persist_doc(doc: dict[str, Any]) -> bool:
    """Write one status document to Mongo. Always safe to call from a worker thread."""
    try:
        col = sat_mongo.col("ingest_status", ensure=False)
        if col is None:
            print("ingest_status persist skipped: no mongo collection", flush=True)
            return False
        payload = {k: v for k, v in doc.items() if k != "_id"}
        col.replace_one({"_id": DOC_ID}, {**payload, "_id": DOC_ID}, upsert=True)
        _cache_doc(payload)
        print(f"ingest_status persist ok cycle_id={payload.get('cycle_id')} phase={payload.get('phase')}", flush=True)
        return True
    except Exception as exc:
        print(f"ingest_status persist failed: {type(exc).__name__}: {exc}", flush=True)
        return False


def load_mongo_doc(*, timeout_s: float = 1.5) -> dict[str, Any] | None:
    """Read ingest_status from Mongo (or the in-process cache). Never call col() on the event loop."""
    if _on_event_loop():
        hit = cached_mongo_doc()
        if hit is not None:
            return hit
        try:
            from concurrent.futures import ThreadPoolExecutor

            with ThreadPoolExecutor(max_workers=1) as pool:
                return pool.submit(_load_mongo_doc_blocking).result(timeout=timeout_s)
        except Exception:
            return cached_mongo_doc()
    return _load_mongo_doc_blocking()


def _load_mongo_doc_blocking() -> dict[str, Any] | None:
    try:
        col = sat_mongo.col("ingest_status")
        if col is None:
            return cached_mongo_doc()
        doc = col.find_one({"_id": DOC_ID}, {"_id": 0}, max_time_ms=1500)
        if isinstance(doc, dict):
            _cache_doc(doc)
            return doc
    except Exception as exc:
        print(f"ingest_status mongo read failed: {type(exc).__name__}: {exc}", flush=True)
    return cached_mongo_doc()


def _mongo_status_doc() -> dict[str, Any] | None:
    """Short-lived cache so the API picks up a just-finished ingest cycle."""
    hit = cached_mongo_doc(max_age_s=_MONGO_VIEW_TTL_S)
    if hit is not None:
        return hit
    return load_mongo_doc(timeout_s=1.0) or cached_mongo_doc(max_age_s=None)


def _ensure_writer() -> None:
    global _writer_thread
    if _writer_thread is not None and _writer_thread.is_alive():
        return
    _writer_thread = threading.Thread(target=_writer_loop, name="ingest-status-writer", daemon=True)
    _writer_thread.start()


def _writer_loop() -> None:
    while True:
        item = _persist_q.get()
        if item is None:
            continue
        kind, payload, event = item
        try:
            if kind == "doc":
                persist_doc(payload)
        finally:
            if event is not None:
                event.set()


def flush_persist(*, timeout_s: float = 5.0) -> bool:
    """Wait until earlier queued writes have been attempted. No-op if we are not persisting."""
    if not _should_persist():
        return False
    _ensure_writer()
    done = threading.Event()
    _persist_q.put((_FLUSH, None, done))
    return bool(done.wait(timeout_s))


def mem_doc() -> dict[str, Any]:
    with _lock:
        return dict(_MEM)


def _write(doc: dict[str, Any]) -> None:
    """Update in-process memory immediately; persist to Mongo off the event loop."""
    with _lock:
        _MEM.clear()
        _MEM.update(doc)
    if not _should_persist():
        return
    _ensure_writer()
    _persist_q.put(("doc", dict(doc), None))

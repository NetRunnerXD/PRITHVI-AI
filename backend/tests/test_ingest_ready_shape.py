"""Defensive /api/ready ingest snapshot and build_core memory fix."""

from __future__ import annotations

import inspect
from unittest.mock import patch

from app.store.ingest_status import _MEM, _lock, empty_snapshot, snapshot

SHAPE_KEYS = {
    "cycle_id",
    "phase",
    "ready",
    "stale",
    "message",
    "satellites",
    "started_ms",
    "updated_ms",
    "finished_at",
    "data_time",
    "age_s",
    "as_of",
}


def _assert_shape(snap: dict) -> None:
    assert isinstance(snap, dict)
    missing = SHAPE_KEYS - set(snap)
    assert not missing, missing
    assert isinstance(snap["satellites"], list)
    assert all(isinstance(s, dict) for s in snap["satellites"])
    assert isinstance(snap["phase"], str)
    assert isinstance(snap["ready"], bool)
    assert isinstance(snap["stale"], bool)


def test_empty_and_default_snapshot_shape():
    _assert_shape(empty_snapshot())
    _assert_shape(snapshot())


def test_snapshot_when_mongo_col_raises():
    with patch("app.store.ingest_status.sat_mongo.col", side_effect=RuntimeError("no mongo")):
        _assert_shape(snapshot())


def test_snapshot_coerces_malformed_satellites_and_started_ms():
    with _lock:
        prev = dict(_MEM)
        _MEM["satellites"] = "not-a-list"
        _MEM["started_ms"] = "bad"
    try:
        with patch("app.store.ingest_status.sat_mongo.col", return_value=None):
            snap = snapshot()
        _assert_shape(snap)
        assert snap["satellites"] == []
        assert snap["age_s"] is None
    finally:
        with _lock:
            _MEM.clear()
            _MEM.update(prev)


def test_snapshot_drops_non_dict_satellite_rows():
    with _lock:
        prev = dict(_MEM)
        _MEM["satellites"] = [{"id": "imd_ir1", "status": "ok"}, "oops", None, 3]
    try:
        with patch("app.store.ingest_status.sat_mongo.col", return_value=None):
            snap = snapshot()
        _assert_shape(snap)
        assert snap["satellites"] == [{"id": "imd_ir1", "status": "ok"}]
    finally:
        with _lock:
            _MEM.clear()
            _MEM.update(prev)


def test_snapshot_never_raises_when_inner_build_fails():
    with patch("app.store.ingest_status._snapshot", side_effect=RuntimeError("boom")):
        _assert_shape(snapshot())


def test_ready_includes_ingest_when_mongo_fails():
    from fastapi.testclient import TestClient
    from app.main import app

    client = TestClient(app)
    with patch("app.store.ingest_status.sat_mongo.col", side_effect=RuntimeError("no mongo")):
        r = client.get("/api/ready")
    assert r.status_code == 200
    body = r.json()
    assert "ingest" in body
    _assert_shape(body["ingest"])


def test_ready_includes_ingest_when_snapshot_raises():
    from fastapi.testclient import TestClient
    from app.main import app

    client = TestClient(app)
    with patch("app.store.ingest_status.snapshot", side_effect=RuntimeError("boom")):
        r = client.get("/api/ready")
    assert r.status_code == 200
    body = r.json()
    assert "ingest" in body
    _assert_shape(body["ingest"])


def test_build_core_does_not_spawn_background_full_build():
    from app.services import snapshot as snap_mod

    src = inspect.getsource(snap_mod.build_core)
    assert "create_task" not in src
    assert "build_snapshot(" not in src

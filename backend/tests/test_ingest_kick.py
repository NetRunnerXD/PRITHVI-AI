"""API → ingest HTTP kick, throttle, embedded mode, stale due_token, Mongo overlay."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from app.ingest.kick import THROTTLE_S, build_kick_request, ingest_base_url, should_throttle
from app.ingest.worker import due_token, embedded_mode
from app.store import ingest_status


def test_build_kick_request_includes_secret_when_set():
    url, params = build_kick_request("https://prithvi-ai-ingest.onrender.com/", "s3cret")
    assert url == "https://prithvi-ai-ingest.onrender.com/api/ingest/trigger"
    assert params == {"background": "true", "secret": "s3cret"}
    url, params = build_kick_request("https://prithvi-ai-ingest.onrender.com")
    assert "secret" not in params
    assert params["background"] == "true"


def test_kick_throttled_to_ten_minutes():
    assert should_throttle(0.0, 1.0) is False
    assert should_throttle(100.0, 100.0 + THROTTLE_S - 1) is True
    assert should_throttle(100.0, 100.0 + THROTTLE_S) is False


def test_ingest_base_url_prefers_env(monkeypatch):
    monkeypatch.setenv("INGEST_BASE_URL", "https://prithvi-ai-ingest.onrender.com")
    assert ingest_base_url() == "https://prithvi-ai-ingest.onrender.com"


def test_embedded_mode_auto_off_when_ingest_url_or_cloud(monkeypatch):
    monkeypatch.delenv("INGEST_EMBEDDED", raising=False)
    monkeypatch.setenv("INGEST_BASE_URL", "https://prithvi-ai-ingest.onrender.com")
    monkeypatch.delenv("CLOUD_LIGHT", raising=False)
    assert embedded_mode() == "off"
    monkeypatch.delenv("INGEST_BASE_URL", raising=False)
    monkeypatch.setenv("CLOUD_LIGHT", "1")
    monkeypatch.setenv("INGEST_EMBEDDED", "auto")
    assert embedded_mode() == "off"
    monkeypatch.setenv("INGEST_EMBEDDED", "1")
    assert embedded_mode() == "on"


def test_due_token_runs_when_stale_even_if_slot_file_exists(monkeypatch, tmp_path):
    from datetime import datetime, timezone
    from app.ingest.worker import IST

    monkeypatch.setenv("INGEST_SLOT_DIR", str(tmp_path))
    now = datetime(2026, 10, 21, 12, 7, tzinfo=IST).astimezone(timezone.utc)
    (tmp_path / "2026-10-21T1200.json").write_text("{}", encoding="utf-8")
    assert due_token(now, set()) is None
    assert due_token(now, set(), is_stale=True) == "2026-10-21T1200"
    assert due_token(now, {"2026-10-21T1200"}, is_stale=True) == "2026-10-21T1200:stale"
    assert due_token(now, {"2026-10-21T1200", "2026-10-21T1200:stale"}, is_stale=True) is None


def test_snapshot_prefers_newer_memory_over_stale_mongo():
    class _Col:
        def find_one(self, *args, **kwargs):
            return {
                "cycle_id": None,
                "phase": "idle",
                "ready": True,
                "satellites": [],
                "updated_ms": 1,
                "started_ms": None,
            }

    with ingest_status._lock:
        prev = dict(ingest_status._MEM)
        ingest_status._MEM.update(
            {
                "cycle_id": "abc123def456",
                "phase": "fetching",
                "ready": False,
                "message": "Analyzing",
                "satellites": [{"id": "imd_ir1", "name": "INSAT", "status": "fetching"}],
                "started_ms": 100,
                "updated_ms": 200,
            }
        )
    try:
        now_ms = ingest_status.ms(ingest_status.now_utc())
        with ingest_status._lock:
            ingest_status._MEM["started_ms"] = now_ms
            ingest_status._MEM["updated_ms"] = now_ms + 50
        with patch("app.store.ingest_status.sat_mongo.col", return_value=_Col()):
            with patch("app.store.ingest_status._overlay_mongo", return_value=True):
                snap = ingest_status._snapshot()
        assert snap["cycle_id"] == "abc123def456"
        assert snap["phase"] == "fetching"
        assert snap["satellites"][0]["id"] == "imd_ir1"
    finally:
        with ingest_status._lock:
            ingest_status._MEM.clear()
            ingest_status._MEM.update(prev)


def test_snapshot_uses_fresher_mongo_doc():
    class _Col:
        def find_one(self, *args, **kwargs):
            return {
                "cycle_id": "frommongo",
                "phase": "ready",
                "ready": True,
                "satellites": [{"id": "imerg", "status": "ok"}],
                "updated_ms": 500,
                "started_ms": 400,
            }

    with ingest_status._lock:
        prev = dict(ingest_status._MEM)
        ingest_status._MEM.update(
            {
                "cycle_id": "oldmem",
                "phase": "idle",
                "ready": True,
                "satellites": [],
                "started_ms": 10,
                "updated_ms": 10,
            }
        )
    try:
        now_ms = ingest_status.ms(ingest_status.now_utc())
        with ingest_status._lock:
            ingest_status._MEM["updated_ms"] = now_ms - 1000
            ingest_status._MEM["started_ms"] = now_ms - 2000
        # fresher mongo
        col_doc_time = now_ms
        class _Fresh:
            def find_one(self, *args, **kwargs):
                return {
                    "cycle_id": "frommongo",
                    "phase": "ready",
                    "ready": True,
                    "satellites": [{"id": "imerg", "status": "ok"}],
                    "updated_ms": col_doc_time,
                    "started_ms": col_doc_time - 100,
                }
        with patch("app.store.ingest_status.sat_mongo.col", return_value=_Fresh()):
            with patch("app.store.ingest_status._overlay_mongo", return_value=True):
                snap = ingest_status._snapshot()
        assert snap["cycle_id"] == "frommongo"
        assert snap["satellites"][0]["id"] == "imerg"
    finally:
        with ingest_status._lock:
            ingest_status._MEM.clear()
            ingest_status._MEM.update(prev)


def test_ready_reports_mongo_configured_bool():
    from fastapi.testclient import TestClient
    from app.main import app

    client = TestClient(app)
    r = client.get("/api/ready")
    assert r.status_code == 200
    body = r.json()
    assert "mongo_configured" in body
    assert body["mongo_configured"] in {True, False}


def test_cloud_storm_map_does_not_rebuild_when_pack_missing(monkeypatch):
    from fastapi.testclient import TestClient
    from app.main import app

    monkeypatch.setenv("CLOUD_LIGHT", "1")
    built = {"n": 0}

    async def _boom(*args, **kwargs):
        built["n"] += 1
        raise AssertionError("must not rebuild IR on the API")

    with (
        patch("app.store.shared_packs.load_storm", return_value=None),
        patch("app.science.storm_map.build", _boom),
        patch("app.config.cloud_light", return_value=True),
    ):
        client = TestClient(app)
        r = client.get("/api/nowcast/storm-map", params={"state": "West Bengal", "past_h": 6})
    assert r.status_code == 200
    body = r.json()
    assert body["source"] == "ingest-pack-pending"
    assert built["n"] == 0

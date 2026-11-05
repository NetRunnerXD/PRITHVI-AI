import json
from datetime import datetime, timezone

from app.ingest.worker import IST, due_token, record_slot_frame, sleep_s


def _ist(h, m):
    return datetime(2026, 10, 21, h, m, tzinfo=IST).astimezone(timezone.utc)


def test_startup_runs_only_when_slot_file_missing(monkeypatch, tmp_path):
    monkeypatch.setenv("INGEST_SLOT_DIR", str(tmp_path))
    now = _ist(12, 7)
    assert due_token(now, set()) == "2026-10-21T1200"
    (tmp_path / "2026-10-21T1200.json").write_text("{}", encoding="utf-8")
    assert due_token(now, set()) is None
    assert sleep_s(now, set()) > 20 * 60


def test_jpeg_time_closes_slot_only_when_inside(monkeypatch, tmp_path):
    monkeypatch.setenv("INGEST_SLOT_DIR", str(tmp_path))
    now = _ist(12, 7)
    assert record_slot_frame(jpeg_time="2026-10-21T06:10:00+00:00", now=now) is False
    assert not (tmp_path / "2026-10-21T1200.json").exists()
    assert record_slot_frame(jpeg_time="2026-10-21T06:32:00+00:00", now=now) is True
    blob = json.loads((tmp_path / "2026-10-21T1200.json").read_text(encoding="utf-8"))
    assert blob["products"]["jpeg"] == "2026-10-21T06:32:00+00:00"


def test_snapshot_uses_product_time_without_a_cycle(monkeypatch, tmp_path):
    monkeypatch.setenv("INGEST_SLOT_DIR", str(tmp_path))
    (tmp_path / "2026-10-21T1200.json").write_text(
        json.dumps({"products": {"jpeg": "2026-10-21T06:32:00+00:00"}, "downloaded_at": "2026-10-21T06:40:00+00:00"}),
        encoding="utf-8",
    )
    from app.store import ingest_status

    ingest_status._MEM["finished_at"] = None
    ingest_status._MEM["data_time"] = None
    snap = ingest_status.snapshot()
    assert snap["data_time"] == "2026-10-21T06:32:00+00:00"
    assert snap["finished_at"] == "2026-10-21T06:40:00+00:00"


def test_late_product_retries_once_then_waits(monkeypatch, tmp_path):
    monkeypatch.setenv("INGEST_SLOT_DIR", str(tmp_path))
    early = _ist(12, 2)
    attempted = set()
    token = due_token(early, attempted)
    assert token == "2026-10-21T1200"
    attempted.add(token)
    assert due_token(_ist(12, 5), attempted) is None
    assert due_token(_ist(12, 11), attempted) == "2026-10-21T1200:retry"
    attempted.add("2026-10-21T1200:retry")
    assert due_token(_ist(12, 20), attempted) is None
    assert sleep_s(_ist(12, 20), attempted) > 9 * 60

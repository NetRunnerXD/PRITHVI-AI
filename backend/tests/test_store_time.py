from datetime import datetime, timedelta, timezone

from app.store.hazard_events import slim_event
from app.store.time import clamp_horizon, iso_z, ms, parse_any


def test_iso_z_strips_ist_offset():
    ist = timezone(timedelta(hours=5, minutes=30))
    t = datetime(2026, 9, 13, 17, 30, tzinfo=ist)
    assert iso_z(t) == "2026-09-13T12:00:00Z"
    assert parse_any("2026-09-13T17:30:00+05:30") is not None
    assert ms(t) == ms(parse_any("2026-09-13T12:00:00Z"))


def test_parse_z_and_naive_utc():
    a = parse_any("2026-09-13T12:00:00Z")
    b = parse_any("2026-09-13T12:00:00")
    assert a is not None and b is not None
    assert abs((a - b).total_seconds()) < 1


def test_clamp_horizon_only_allowed():
    assert clamp_horizon(1) == 1
    assert clamp_horizon(3) == 3
    assert clamp_horizon(6) == 6
    assert clamp_horizon(12) == 12
    assert clamp_horizon(24) == 6
    assert clamp_horizon("nope") == 6


def test_events_same_point_stay_separate():
    a = slim_event(
        {
            "lat": 22.5,
            "lon": 88.3,
            "kind": "storm",
            "started_ms": 1_000,
            "closes_ms": 2_000,
            "event_id": "evt-a",
        }
    )
    b = slim_event(
        {
            "lat": 22.5,
            "lon": 88.3,
            "kind": "storm",
            "started_ms": 3_000,
            "closes_ms": 4_000,
            "event_id": "evt-b",
        }
    )
    assert a is not None and b is not None
    assert a["event_id"] != b["event_id"]
    assert a["started_ms"] != b["started_ms"]

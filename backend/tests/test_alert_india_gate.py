from app.providers.gdacs import parse_events
from app.services.alerts import india_affects, is_live
from datetime import datetime, timedelta, timezone


def test_gdacs_drops_philippines_and_indonesia():
    rows = [
        {"eventtype": "TC", "latitude": 14.6, "longitude": 121.0, "name": "Philippines", "eventid": "ph1", "country": "Philippines"},
        {"eventtype": "EQ", "latitude": -0.5, "longitude": 100.3, "name": "Sumatra Indonesia", "eventid": "id1", "country": "Indonesia"},
        {"eventtype": "FL", "latitude": 26.2, "longitude": 91.7, "name": "Assam flood", "eventid": "in1", "country": "India", "alertlevel": "Orange"},
        {"eventtype": "TC", "latitude": 19.8, "longitude": 86.0, "name": "Odisha", "eventid": "in2", "country": "India", "alertlevel": "Red"},
    ]
    out = parse_events(rows)
    titles = " ".join(r["title"] for r in out).lower()
    assert "philippines" not in titles
    assert "indonesia" not in titles
    assert any("assam" in (r["title"] or "").lower() or "india" in (r.get("title") or "").lower() for r in out)


def test_india_affects_text():
    assert not india_affects({"title": "Flood warning Philippines", "body": "Manila"})
    assert india_affects({"title": "Flood warning Assam", "body": "India"})
    assert india_affects({"title": "IMD", "body": "Odisha", "source": "imd-cap"})


def test_is_live_expiry():
    now = datetime(2026, 9, 1, tzinfo=timezone.utc)
    old = (now - timedelta(days=10)).isoformat()
    fresh = (now - timedelta(hours=2)).isoformat()
    assert not is_live({"issued_at": old}, now=now, kind="rainfall")
    assert is_live({"issued_at": fresh}, now=now, kind="rainfall")
    assert not is_live({"expires_at": (now - timedelta(hours=1)).isoformat()}, now=now)

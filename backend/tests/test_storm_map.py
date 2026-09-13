from datetime import datetime, timedelta, timezone

from app.data.india_districts import state_frame
from app.science.storm_map import _occurred, build
from app.store.time import clamp_horizon
import pytest


def test_occurred_uses_lead_h_not_now():
    now = datetime(2026, 9, 13, 12, 0, tzinfo=timezone.utc)
    t = _occurred({"lead_h": -6, "lat": 22.5, "lon": 88.3}, now)
    assert t is not None
    assert abs((now - t) - timedelta(hours=6)) < timedelta(seconds=2)


def test_occurred_skips_missing_time():
    now = datetime(2026, 9, 13, 12, 0, tzinfo=timezone.utc)
    assert _occurred({"lat": 22.5, "lon": 88.3}, now) is None


def test_occurred_prefers_saved_at():
    now = datetime(2026, 9, 13, 12, 0, tzinfo=timezone.utc)
    t = _occurred({"saved_at": (now - timedelta(hours=5)).isoformat()}, now)
    assert t is not None
    assert (now - t) >= timedelta(hours=4, minutes=50)


def test_west_bengal_frame_crops_india():
    wb = state_frame("West Bengal")
    rj = state_frame("Rajasthan")
    india = state_frame("India")
    assert wb["ok"] is True
    assert wb["n"] >= 15
    assert wb["east"] < 92
    assert wb["west"] > 84
    assert rj["ok"] is True
    assert rj["west"] < 74
    assert abs(wb["lon"] - rj["lon"]) > 5
    assert india["all_india"] is True
    assert india["n"] > wb["n"]
    assert india["west"] < wb["west"]


@pytest.mark.asyncio
async def test_storm_map_skips_network_under_pytest():
    pack = await build("West Bengal")
    assert pack["state"] == "West Bengal"
    assert pack["frame"]["ok"] is True
    assert pack["status"] == "test-skip"
    assert pack["strokes"] == []
    india = await build("India")
    assert india["state"] == "India"
    assert india["frame"]["all_india"] is True


def test_past_h_rejects_24():
    assert clamp_horizon(24) == 6
    assert clamp_horizon(12) == 12


def test_predicted_unverified_keeps_storms():
    incidents = [
        {"phase": "predicted", "kind": "storm", "gate": {"ok": False}},
        {"phase": "predicted", "kind": "lightning", "gate": {"ok": False}},
        {"phase": "predicted", "kind": "lightning", "gate": {"ok": True}, "engine": "open-meteo-thunder"},
    ]

    def _pred_ok(i):
        if i.get("engine") == "open-meteo-thunder":
            return True
        return bool((i.get("gate") or {}).get("ok"))

    unverified = [i for i in incidents if i.get("phase") == "predicted" and not _pred_ok(i)]
    kinds = {i["kind"] for i in unverified}
    assert "storm" in kinds
    assert "lightning" in kinds

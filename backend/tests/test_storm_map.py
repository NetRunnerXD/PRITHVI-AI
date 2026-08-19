from app.data.india_districts import state_frame
from app.science.storm_map import build
import pytest


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

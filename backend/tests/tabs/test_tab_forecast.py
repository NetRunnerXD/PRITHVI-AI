"""Forecast / outlook / scan stay inside the asked state."""

import pytest

from app.data.india_districts import districts_in_state
from app.services.scan import rank_districts
from .isolation import loc


def test_wb_scan_contains_only_west_bengal():
    rows = districts_in_state("West Bengal")
    assert rows
    assert all(r["state"] == "West Bengal" for r in rows)
    assert not any(r["state"] == "Chhattisgarh" for r in rows)


def test_contradiction_howrah_is_not_a_state_scan():
    """Passing a town as the scan state must not spill into all-India / Chhattisgarh."""
    rows = districts_in_state("Howrah")
    assert rows == []


@pytest.mark.asyncio
async def test_rank_howrah_state_is_empty_not_india(monkeypatch):
    async def boom(row):
        raise AssertionError(f"must not fetch {row['district']}")

    monkeypatch.setattr("app.services.scan._one", boom)
    out = await rank_districts("Howrah", metric="flood", limit=10)
    assert out.get("ranked") == []
    assert out.get("error") == "unknown_state"


@pytest.mark.asyncio
async def test_rank_west_bengal_never_lists_raipur(monkeypatch):
    async def fake_one(row):
        return {
            **row,
            "ok": True,
            "precip_3d_mm": 10,
            "soil_m3m3": 0.3,
            "temp_max_c": 31,
            "flood_score": 20,
            "drought_score": 10,
            "irrigation_need": 5,
        }

    monkeypatch.setattr("app.services.scan._one", fake_one)
    out = await rank_districts("West Bengal", metric="flood", limit=30)
    names = {r["district"] for r in out["ranked"]}
    states = {r["state"] for r in out["ranked"]}
    assert states == {"West Bengal"}
    assert "Raipur" not in names
    assert "Howrah" in names or loc("Howrah").district in names

"""Browser Open-Meteo packs seed the server cache and skip outbound forecast."""

import time

import pytest

from app import cache
from app.providers import open_meteo


@pytest.fixture(autouse=True)
def _clear():
    cache.clear()
    yield
    cache.clear()


def _fc():
    return {
        "current": {"temperature_2m": 31.2, "precipitation": 0.0},
        "hourly": {"time": ["2026-09-10T00:00"], "precipitation": [0.1]},
        "daily": {"time": ["2026-09-10"], "precipitation_sum": [2.0]},
    }


@pytest.mark.asyncio
async def test_seed_then_forecast_does_not_http(monkeypatch):
    called = {"n": 0}

    class _Boom:
        async def get(self, *a, **k):
            called["n"] += 1
            raise AssertionError("should not hit Open-Meteo")

    monkeypatch.setattr(open_meteo, "client", lambda: _Boom())
    assert open_meteo.seed_from_client(22.07, 88.07, {"forecast": _fc()}, time.time())
    data = await open_meteo.forecast(22.07, 88.07)
    assert data["current"]["temperature_2m"] == 31.2
    assert called["n"] == 0


def test_stale_pack_not_seeded():
    old = time.time() - 10_000
    assert not open_meteo.seed_from_client(22.07, 88.07, {"forecast": _fc()}, old)
    assert not open_meteo.client_seeded(22.07, 88.07)


@pytest.mark.asyncio
async def test_seed_skips_blend_http(monkeypatch):
    called = {"n": 0}

    class _Boom:
        async def get(self, *a, **k):
            called["n"] += 1
            raise AssertionError("blend http")

    monkeypatch.setattr(open_meteo, "client", lambda: _Boom())
    open_meteo.seed_from_client(22.07, 88.07, {"forecast": _fc()}, time.time())
    out = await open_meteo.forecast_models(22.07, 88.07)
    assert "best_match" in out
    assert called["n"] == 0


@pytest.mark.asyncio
async def test_seed_flood_marine_era5_skips_http(monkeypatch):
    called = {"n": 0}

    class _Boom:
        async def get(self, *a, **k):
            called["n"] += 1
            raise AssertionError("extra om http")

    monkeypatch.setattr(open_meteo, "client", lambda: _Boom())
    flood = {"daily": {"time": ["2026-09-10"], "river_discharge": [1.0]}}
    marine = {"current": {"wave_height": 1.2}}
    era5 = {"ok": True, "precip_days": [1.0], "z500_m": 5800}
    models = {
        "ifs025": {"daily": {"time": ["2026-09-10"], "precipitation_sum": [2.0]}, "hourly": {}},
    }
    assert open_meteo.seed_from_client(
        22.07,
        88.07,
        {"forecast": _fc(), "flood": flood, "marine": marine, "era5": era5, "models": models},
        time.time(),
    )
    assert (await open_meteo.flood(22.07, 88.07))["daily"]["river_discharge"] == [1.0]
    assert (await open_meteo.marine(22.07, 88.07))["current"]["wave_height"] == 1.2
    era = await open_meteo.era5_context(22.07, 88.07)
    assert era.get("z500_m") == 5800
    blended = await open_meteo.forecast_models(22.07, 88.07)
    assert "ifs025" in blended
    assert called["n"] == 0


def test_seed_usgs_and_nasa():
    from app.providers import hazards, nasa_power

    assert hazards.seed_usgs_csv("time,latitude,longitude,mag,place\n")
    assert cache.get("usgs:india:csv")
    payload = {"properties": {"parameter": {"PRECTOTCORR": {"20260901": 1.2}}}}
    assert nasa_power.seed_from_client(22.07, 88.07, payload)
    assert cache.get("nasa:22.07:88.07:16")["properties"]["parameter"]["PRECTOTCORR"]["20260901"] == 1.2

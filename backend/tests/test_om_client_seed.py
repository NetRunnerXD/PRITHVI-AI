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

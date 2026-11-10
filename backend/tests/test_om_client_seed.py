"""Browser Open-Meteo packs seed the server cache and skip outbound forecast."""

import time

import pytest

from app import cache
from app.providers import open_meteo
from app.services import snapshot_obs


@pytest.fixture(autouse=True)
def _clear():
    cache.clear()
    yield
    cache.clear()


def _fc(lat=22.07, lon=88.07, temp=31.2):
    return {
        "latitude": lat,
        "longitude": lon,
        "current": {"temperature_2m": temp, "precipitation": 0.0},
        "hourly": {"time": ["2026-09-10T00:00"], "precipitation": [0.1], "temperature_2m": [temp]},
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
    assert data.get("_client_seed") is True
    assert called["n"] == 0


def test_stale_pack_not_seeded():
    old = time.time() - 10_000
    assert not open_meteo.seed_from_client(22.07, 88.07, {"forecast": _fc()}, old)
    assert not open_meteo.client_seeded(22.07, 88.07)


def test_pack_older_than_two_hours_rejected():
    old = time.time() - (2 * 3600 + 30)
    assert not open_meteo.seed_from_client(22.07, 88.07, {"forecast": _fc()}, old)


def test_coord_mismatch_rejected():
    pack = _fc(lat=22.07, lon=88.07)
    pack["latitude"] = 22.07 + 0.5
    assert not open_meteo.seed_from_client(22.07, 88.07, {"forecast": pack}, time.time())
    assert not open_meteo.client_seeded(22.07, 88.07)


def test_coord_within_tolerance_accepted():
    pack = _fc(lat=22.07, lon=88.07)
    pack["latitude"] = 22.07 + 0.05
    pack["longitude"] = 88.07 - 0.04
    assert open_meteo.seed_from_client(22.07, 88.07, {"forecast": pack}, time.time())


def test_oversized_pack_rejected():
    pack = _fc()
    pack["hourly"]["padding"] = "x" * 1_000_000
    assert not open_meteo.seed_from_client(22.07, 88.07, {"forecast": pack}, time.time())


def test_climatology_pack_rejected():
    pack = _fc()
    pack["source"] = "india-climatology"
    pack["_stale"] = True
    assert not open_meteo.seed_from_client(22.07, 88.07, {"forecast": pack}, time.time())


def test_seed_stays_on_rounded_pin():
    assert open_meteo.seed_from_client(22.07, 88.07, {"forecast": _fc(temp=31.2)}, time.time())
    assert open_meteo.client_seeded(22.07, 88.07)
    assert not open_meteo.client_seeded(22.30, 88.07)
    assert cache.get(open_meteo._om_key("fc4", 22.30, 88.07)) is None


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


@pytest.mark.asyncio
async def test_gather_marks_client_status(monkeypatch):
    from app.schemas.location import Location

    loc = Location(
        id="t",
        label="T",
        state="WB",
        district="East Medinipur",
        lat=22.07,
        lon=88.07,
        place_name="Haldia",
    )

    class _Boom:
        async def get(self, *a, **k):
            raise AssertionError("no http")

    monkeypatch.setattr(open_meteo, "client", lambda: _Boom())
    assert open_meteo.seed_from_client(22.07, 88.07, {"forecast": _fc()}, time.time())
    obs = await snapshot_obs.gather_observations(loc, enrich=False)
    assert obs["status"]["open-meteo"] == "client"
    assert obs["om"]["current"]["temperature_2m"] == 31.2


@pytest.mark.asyncio
async def test_seed_invalidates_stale_snapshot():
    from app.schemas.dashboard import DashboardSnapshot
    from app.schemas.location import Location
    from app.services import snapshot as snapmod

    loc = Location(
        id="t",
        label="Haldia, West Bengal",
        state="West Bengal",
        district="Purba Medinipur",
        lat=22.07,
        lon=88.07,
        place_name="Haldia",
    )
    stale = DashboardSnapshot.model_construct(
        location=loc,
        generated_at="2026-11-11T00:00:00+05:30",
        provider_status={"open-meteo": "stale"},
        enriching=False,
    )
    cache.set(snapmod.pin_key(loc), stale, 600, 3600)
    assert snapmod.peek_snapshot(loc) is stale
    assert open_meteo.seed_from_client(22.07, 88.07, {"forecast": _fc()}, time.time())
    assert snapmod.peek_snapshot(loc) is None


def test_seed_usgs_and_nasa():
    from app.providers import hazards, nasa_power

    assert hazards.seed_usgs_csv("time,latitude,longitude,mag,place\n")
    assert cache.get("usgs:india:csv")
    payload = {"properties": {"parameter": {"PRECTOTCORR": {"20260901": 1.2}}}}
    assert nasa_power.seed_from_client(22.07, 88.07, payload)
    assert cache.get("nasa:22.07:88.07:16")["properties"]["parameter"]["PRECTOTCORR"]["20260901"] == 1.2

"""Live Open-Meteo forecast retries once, then falls back without poisoning caches."""

from __future__ import annotations

import asyncio
import time
import pytest

from app import cache
from app.providers import open_meteo
from app.services import snapshot as snapmod
from app.services import snapshot_obs


@pytest.fixture(autouse=True)
def _reset(monkeypatch, tmp_path):
    cache.clear()
    monkeypatch.setattr(open_meteo, "_GOOD", tmp_path / "om_last")
    monkeypatch.setattr(open_meteo, "LIVE_RETRY_BACKOFF_S", 0.0)
    monkeypatch.setattr(snapshot_obs, "OM_RETRY_BACKOFF_S", 0.0)
    yield
    cache.clear()


def _live_pack():
    return {
        "current": {"temperature_2m": 31.2, "precipitation": 0.0},
        "hourly": {"time": ["2026-11-11T00:00"], "precipitation": [0.1]},
        "daily": {"time": ["2026-11-11"], "precipitation_sum": [2.0]},
    }


class _Resp:
    def __init__(self, status_code=200, payload=None, error=None):
        self.status_code = status_code
        self._payload = payload if payload is not None else _live_pack()
        self._error = error

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"http {self.status_code}")

    def json(self):
        if self._error:
            return {"error": self._error}
        return self._payload


class _Scripted:
    def __init__(self, answers):
        self.answers = list(answers)
        self.calls = 0

    async def get(self, *a, **k):
        self.calls += 1
        if not self.answers:
            raise AssertionError("unexpected extra GET")
        item = self.answers.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


@pytest.mark.asyncio
async def test_forecast_retries_once_then_succeeds(monkeypatch):
    scripted = _Scripted([RuntimeError("boom"), _Resp()])
    monkeypatch.setattr(open_meteo, "client", lambda: scripted)
    data = await open_meteo.forecast(22.07, 88.07)
    assert data["current"]["temperature_2m"] == 31.2
    assert not data.get("_stale")
    assert scripted.calls == 2


@pytest.mark.asyncio
async def test_forecast_retries_429_before_fallback(monkeypatch):
    scripted = _Scripted([_Resp(status_code=429), _Resp()])
    monkeypatch.setattr(open_meteo, "client", lambda: scripted)
    data = await open_meteo.forecast(22.07, 88.07)
    assert data["current"]["temperature_2m"] == 31.2
    assert scripted.calls == 2


@pytest.mark.asyncio
async def test_climatology_not_saved_as_good_and_cache_is_short(monkeypatch):
    scripted = _Scripted([RuntimeError("down"), RuntimeError("down")])
    monkeypatch.setattr(open_meteo, "client", lambda: scripted)

    async def no_archive(*a, **k):
        return None

    monkeypatch.setattr(open_meteo, "_archive_fallback", no_archive)
    data = await open_meteo.forecast(11.11, 77.01)
    assert data.get("source") == "india-climatology"
    assert data.get("_stale") is True
    assert open_meteo._load_good("fc", 11.11, 77.01) is None
    key = f"om:fc4:{round(11.11, 3)}:{round(77.01, 3)}"
    hit = cache._store.get(key)
    assert hit is not None
    fresh, swr, _val = cache._unpack(hit)
    now = time.time()
    assert 0 < fresh - now <= 20
    assert swr - now <= 45


@pytest.mark.asyncio
async def test_gather_retries_open_meteo_after_timeout(monkeypatch):
    calls = {"n": 0}

    async def flaky(lat, lon):
        calls["n"] += 1
        if calls["n"] == 1:
            await asyncio.sleep(0.25)
            raise RuntimeError("too slow")
        pack = _live_pack()
        return pack

    from app.schemas.location import Location

    loc = Location(id="t", label="T", state="WB", district="East Medinipur", lat=22.07, lon=88.07, place_name="Haldia")
    monkeypatch.setattr(snapshot_obs, "OM_RETRY_BACKOFF_S", 0.0)
    monkeypatch.setattr(open_meteo, "forecast", flaky)

    # Patch wait budget down so the first call times out inside run().
    orig_run_waiters = []

    async def tight():
        # Directly exercise run() via gather_observations enrich=False (timeout=2.0).
        # Shrink the first timeout by wrapping wait_for? Use a short sleep and patch timeout
        # by calling run through gather with a monkeypatched wait_for only for the first call.
        return await snapshot_obs.gather_observations(loc, enrich=False)

    # Instead, call the inner run by shortening the core timeout path via a custom wait_for.
    waits = {"n": 0}
    real_wait = asyncio.wait_for

    async def wait_for(aw, timeout=None, **k):
        waits["n"] += 1
        if waits["n"] == 1:
            return await real_wait(aw, timeout=0.05)
        return await real_wait(aw, timeout=timeout)

    monkeypatch.setattr(snapshot_obs.asyncio, "wait_for", wait_for)
    obs = await tight()
    assert calls["n"] == 2
    assert obs["om"]["current"]["temperature_2m"] == 31.2
    assert obs["status"]["open-meteo"] == "ok"


@pytest.mark.asyncio
async def test_climatology_status_is_fallback(monkeypatch):
    from app.schemas.location import Location

    loc = Location(id="t", label="T", state="WB", district="East Medinipur", lat=22.07, lon=88.07, place_name="Haldia")

    async def clim(lat, lon):
        pack = open_meteo._climatological_fallback(lat, lon)
        return pack

    monkeypatch.setattr(open_meteo, "forecast", clim)
    obs = await snapshot_obs.gather_observations(loc, enrich=False)
    assert obs["status"]["open-meteo"] == "fallback"


@pytest.mark.asyncio
async def test_build_snapshot_refresh_bypasses_cache(monkeypatch):
    from app.schemas.location import Location
    from app.schemas.dashboard import DashboardSnapshot

    loc = Location(id="t", label="T", state="WB", district="East Medinipur", lat=22.07, lon=88.07, place_name="Haldia")
    n = {"c": 0}

    def _snap(status: str) -> DashboardSnapshot:
        # Build a minimal model via model_construct to avoid the full assemble graph.
        return DashboardSnapshot.model_construct(
            location=loc,
            generated_at="2026-11-11T00:00:00+05:30",
            provider_status={"open-meteo": status},
            enriching=False,
        )

    async def factory_snap(*a, **k):
        n["c"] += 1
        return _snap("ok" if n["c"] > 1 else "stale")

    monkeypatch.setattr(snapmod, "_assemble_snapshot", factory_snap)
    first = await snapmod.build_snapshot(loc)
    assert first.provider_status["open-meteo"] == "stale"
    assert n["c"] == 1
    # Cached stale pack would normally be reused; refresh must rebuild.
    second = await snapmod.build_snapshot(loc, refresh=True)
    assert n["c"] == 2
    assert second.provider_status["open-meteo"] == "ok"


@pytest.mark.asyncio
async def test_forecast_models_retries_on_error(monkeypatch):
    scripted = _Scripted([RuntimeError("blend down"), _Resp(payload={
        "daily": {"time": ["2026-11-11"], "precipitation_sum_ecmwf_ifs025": [1.0]},
        "hourly": {"time": ["2026-11-11T00:00"], "precipitation_ecmwf_ifs025": [0.0]},
    })])
    monkeypatch.setattr(open_meteo, "client", lambda: scripted)
    out = await open_meteo.forecast_models(22.07, 88.07)
    assert "ifs025" in out
    assert scripted.calls == 2


def test_cache_delete_drops_key():
    cache.set("x", {"v": 1}, 60, 60)
    assert cache.get("x") == {"v": 1}
    cache.delete("x")
    assert cache.get("x") is None

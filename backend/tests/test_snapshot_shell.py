import asyncio

from app.services.location_svc import resolve_location
from app.services.snapshot import gather_observations, pin_key, _assemble_snapshot


def test_pin_key_grids():
    a = resolve_location(lat=22.06, lon=88.06)
    b = resolve_location(lat=22.07, lon=88.07)
    assert pin_key(a) == pin_key(b)


def test_shell_gather_skips_blend_members():
    loc = resolve_location(q="Haldia")

    async def _run():
        return await gather_observations(loc, enrich=False)

    obs = asyncio.run(_run())
    assert obs.get("om_models") == {}
    assert obs.get("era5") == {}
    assert "open-meteo" in (obs.get("status") or {})


def test_shell_snapshot_has_current_sky():
    loc = resolve_location(q="Haldia")

    async def _run():
        return await _assemble_snapshot(loc, enrich=False)

    snap = asyncio.run(_run())
    assert snap.enriching is True
    assert snap.descriptive.current is not None
    assert snap.location.place_name == "Haldia"

import asyncio

from app.providers.weather_grid import NX, NY, _uv, mesh, synthetic, world_grid


def test_mesh_covers_world():
    lats, lons, pts = mesh()
    assert len(lats) == NY
    assert len(lons) == NX
    assert len(pts) == NX * NY
    assert min(lats) < 0
    assert max(lats) > 50
    assert min(lons) <= -170
    assert max(lons) >= 170


def test_uv_meteorological():
    u, v = _uv(36.0, 90.0)
    assert u is not None and v is not None
    assert u < 0
    assert abs(v) < 0.2


def test_synthetic_hour_changes_temp():
    a = synthetic(0)
    b = synthetic(12)
    assert a["n"] == NX * NY
    assert a["fields"]["temp_c"][0] != b["fields"]["temp_c"][0]
    assert set(a["products"]) >= {"wind", "temp", "precip", "pressure"}


def test_world_grid_under_pytest_is_synthetic():
    pack = asyncio.run(world_grid(2))
    assert pack["nx"] == NX
    assert len(pack["fields"]["wind_u"]) == pack["n"]
    assert pack["hour"] == 2
    assert pack.get("scope") == "world"

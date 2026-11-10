"""Cloud-safe GFS: skip GRIB decode, serve Open-Meteo-shaped map layers."""

from __future__ import annotations

import io
from unittest.mock import patch

import numpy as np
import pytest
from PIL import Image

from app.providers import gfs
from app.providers.weather_grid import synthetic


def setup_function():
    gfs._STATE.update(cycle=None, fields=None, checked=0.0, status="idle", error=None, source=None)
    gfs._TASK = None


def teardown_function():
    setup_function()


def test_decode_enabled_defaults_and_flags(monkeypatch):
    monkeypatch.delenv("GFS_DECODE_ENABLED", raising=False)
    monkeypatch.delenv("CLOUD_LIGHT", raising=False)
    monkeypatch.delenv("RENDER", raising=False)
    assert gfs.decode_enabled() is True
    monkeypatch.setenv("RENDER", "true")
    assert gfs.decode_enabled() is False
    monkeypatch.delenv("RENDER", raising=False)
    monkeypatch.setenv("CLOUD_LIGHT", "1")
    assert gfs.decode_enabled() is False
    monkeypatch.setenv("GFS_DECODE_ENABLED", "1")
    assert gfs.decode_enabled() is True
    monkeypatch.setenv("GFS_DECODE_ENABLED", "0")
    monkeypatch.delenv("CLOUD_LIGHT", raising=False)
    monkeypatch.delenv("RENDER", raising=False)
    assert gfs.decode_enabled() is False


def test_kick_is_noop_when_decode_disabled(monkeypatch):
    monkeypatch.setenv("GFS_DECODE_ENABLED", "0")
    with patch("asyncio.get_running_loop") as loop:
        gfs.kick()
        loop.assert_not_called()
    assert gfs._STATE["fields"] is None
    st = gfs.status()
    assert st["decode"] is False
    assert "open-meteo" in st["source"].lower()


@pytest.mark.asyncio
async def test_ensure_fills_png_from_open_meteo_grid(monkeypatch):
    monkeypatch.setenv("GFS_DECODE_ENABLED", "0")
    pack = synthetic(0)

    async def fake_grid(hour=0):
        return pack

    monkeypatch.setattr("app.providers.weather_grid.world_grid", fake_grid)
    st = await gfs.ensure(0)
    assert st["ok"] is True
    assert st["decode"] is False
    assert "open-meteo" in st["source"].lower()
    meta = gfs.meta(0)
    assert meta["ok"] is True
    assert meta["step"] in gfs.STEPS
    assert meta["grid"]["nx"] == gfs.NX and meta["grid"]["ny"] == gfs.NY
    blob = gfs.png("temp_c", meta["step"])
    assert blob
    img = np.asarray(Image.open(io.BytesIO(blob)))
    assert img.shape == (gfs.NY, gfs.NX)
    assert gfs.png("cape", meta["step"])
    assert gfs.png("precip_mm", meta["step"])


def test_refresh_does_not_touch_eccodes_when_disabled(monkeypatch):
    monkeypatch.setenv("GFS_DECODE_ENABLED", "0")

    async def fake_fill(hour_ahead=0):
        gfs._STATE.update(status="ok", source="Open-Meteo GFS/IFS (no local GRIB decode)", checked=1.0)
        return gfs.status()

    monkeypatch.setattr(gfs, "_fill_from_open_meteo", fake_fill)
    import asyncio

    st = asyncio.run(gfs.refresh())
    assert st["decode"] is False
    assert "open-meteo" in st["source"].lower()

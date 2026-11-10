"""Cloud-safe satellite lightning: India bbox, no IMERG validate, no API mosaic kick."""

from __future__ import annotations

import asyncio

import pytest

from app.science import sat_lightning as sl


def test_default_bbox_india_on_cloud(monkeypatch):
    monkeypatch.delenv("RENDER", raising=False)
    monkeypatch.delenv("CLOUD_LIGHT", raising=False)
    assert sl.default_bbox() == sl.WORLD_BBOX
    monkeypatch.setenv("CLOUD_LIGHT", "1")
    assert sl.default_bbox() == sl.INDIA_BBOX
    # India mosaic is ~40x smaller than the global 50S–50N frame.
    s, w, n, e = sl.INDIA_BBOX
    gs, gw, gn, ge = sl.WORLD_BBOX
    india = (n - s) / 0.2 * (e - w) / 0.2
    world = (gn - gs) / 0.2 * (ge - gw) / 0.2
    assert india * 20 < world


def test_validate_disabled_on_cloud(monkeypatch):
    monkeypatch.delenv("SATLTG_VALIDATE", raising=False)
    monkeypatch.setenv("CLOUD_LIGHT", "1")
    assert sl.validate_enabled() is False
    monkeypatch.setenv("SATLTG_VALIDATE", "1")
    assert sl.validate_enabled() is True
    monkeypatch.delenv("SATLTG_VALIDATE", raising=False)
    monkeypatch.delenv("CLOUD_LIGHT", raising=False)
    monkeypatch.delenv("RENDER", raising=False)
    assert sl.validate_enabled() is True


@pytest.mark.asyncio
async def test_refresh_skips_validate_on_cloud(monkeypatch):
    monkeypatch.setenv("CLOUD_LIGHT", "1")
    monkeypatch.delenv("SATLTG_VALIDATE", raising=False)
    called = {"validate": 0, "estimate": 0}

    async def fake_estimate(**_k):
        called["estimate"] += 1
        return {"ok": True, "status": "ok", "cells": [{"lat": 22.0, "lon": 88.0, "score": 0.6, "category": "likely"}]}

    async def fake_validate(n_hours=3):
        called["validate"] += 1
        return {"ok": True, "total": {"likely": {"far": 0.2}}}

    from app import cache

    cache.clear()
    monkeypatch.setattr(sl, "estimate", fake_estimate)
    monkeypatch.setattr(sl, "validate", fake_validate)
    pack = await sl.refresh()
    assert called["estimate"] == 1
    assert called["validate"] == 0
    assert pack["ok"] is True
    assert pack["validation"]["status"] == "skipped_on_cloud"
    assert sl.peek(kick=False)["cells"][0]["lat"] == 22.0


def test_peek_does_not_kick_when_cloud_has_stale_pack(monkeypatch):
    import time

    from app import cache

    monkeypatch.setenv("CLOUD_LIGHT", "1")
    cache.clear()
    sl._TASK = None
    cache.set(sl.CK, {"ok": True, "cells": [1], "_ts": time.time() - 20 * 60}, 3600)
    kicked = {"n": 0}

    def boom():
        kicked["n"] += 1
        raise AssertionError("must not kick")

    monkeypatch.setattr(asyncio, "get_running_loop", boom)
    hit = sl.peek(kick=True)
    assert hit and hit["cells"] == [1]
    assert kicked["n"] == 0

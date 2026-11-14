"""Regression tests for the Nov 14 2026 Render issues: dashboard 500s from a leaked
CancelledError, ingest OOM from full-frame decodes, and a blocking /api/ready."""

from __future__ import annotations

import asyncio
import time
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pytest


# ---------------------------------------------------------------- 1. cache single-flight


def test_aget_timeout_of_one_caller_does_not_cancel_others():
    from app import cache

    async def main():
        cache.clear()

        async def slow():
            await asyncio.sleep(0.3)
            return 42

        a = asyncio.create_task(asyncio.wait_for(cache.aget("k1", slow, ttl_s=60), 0.05))
        b = asyncio.create_task(cache.aget("k1", slow, ttl_s=60))
        with pytest.raises(asyncio.TimeoutError):
            await a
        # Previously B got CancelledError (a BaseException) -> "No response returned".
        assert await b == 42
        assert cache.get("k1") == 42

    asyncio.run(main())


def test_aget_cancelled_shared_task_raises_ordinary_exception():
    from app import cache

    async def main():
        cache.clear()

        async def slow():
            await asyncio.sleep(5)

        b = asyncio.create_task(cache.aget("k2", slow, ttl_s=60))
        await asyncio.sleep(0.01)
        cache._inflight["k2"].cancel()
        with pytest.raises(Exception) as ei:
            await b
        assert isinstance(ei.value, cache.SharedFetchCancelled)
        assert "k2" not in cache._inflight

    asyncio.run(main())


def test_aget_skips_dead_inflight_task():
    from app import cache

    async def main():
        cache.clear()

        async def never():
            await asyncio.sleep(5)

        dead = asyncio.create_task(never())
        dead.cancel()
        with pytest.raises(asyncio.CancelledError):
            await dead
        cache._inflight["k3"] = dead  # what a skipped finally used to leave behind

        async def ok():
            return "fresh"

        assert await cache.aget("k3", ok, ttl_s=60) == "fresh"

    asyncio.run(main())


# ---------------------------------------------------------------- 1b. middleware


def _mini_app():
    from fastapi import FastAPI

    from app.middleware import CacheControlMiddleware, HeaderStampMiddleware, JSONErrorMiddleware

    app = FastAPI()

    @app.get("/api/boom")
    async def boom():
        raise ValueError("real cause")

    @app.get("/api/leak")
    async def leak():
        raise asyncio.CancelledError()

    @app.get("/api/dashboard")
    async def dash():
        return {"ok": True}

    app.add_middleware(JSONErrorMiddleware)
    app.add_middleware(CacheControlMiddleware)
    app.add_middleware(HeaderStampMiddleware, version="t1", surface=lambda p, c: "web")
    return app


def test_json_error_middleware_surfaces_real_exception(caplog):
    from fastapi.testclient import TestClient

    c = TestClient(_mini_app(), raise_server_exceptions=False)
    with caplog.at_level("ERROR", logger="prithvi.http"):
        r = c.get("/api/boom")
    assert r.status_code == 500
    assert r.json()["detail"] == "ValueError"
    assert r.headers["cache-control"] == "no-store"
    assert r.headers["x-api-version"] == "t1"
    assert any("ValueError" in (rec.getMessage() + str(rec.exc_info)) for rec in caplog.records)


def test_json_error_middleware_handles_leaked_cancel():
    from fastapi.testclient import TestClient

    c = TestClient(_mini_app(), raise_server_exceptions=False)
    r = c.get("/api/leak")
    assert r.status_code == 500
    assert r.json()["detail"] == "CancelledError"


def test_cache_control_and_stamp_headers():
    from fastapi.testclient import TestClient

    c = TestClient(_mini_app())
    r = c.get("/api/dashboard")
    assert r.status_code == 200
    assert r.headers["cache-control"].startswith("public, max-age=60")
    assert r.headers["x-client-surface"] == "web"
    assert c.get("/api/dashboard?refresh=1").headers["cache-control"] == "no-store"


def test_real_app_has_no_base_http_middleware():
    from starlette.middleware.base import BaseHTTPMiddleware

    from app.main import app

    for m in app.user_middleware:
        assert not (isinstance(m.cls, type) and issubclass(m.cls, BaseHTTPMiddleware)), m.cls


# ---------------------------------------------------------------- 3. /api/ready never blocks


def test_ready_does_not_wait_on_slow_mongo(monkeypatch):
    from fastapi.testclient import TestClient

    from app.main import app
    from app.store import ingest_status

    class SlowCol:
        def find_one(self, *a, **k):
            time.sleep(2.0)
            return {"cycle_id": "abc", "phase": "ready", "updated_ms": 1}

    monkeypatch.setattr(ingest_status, "_overlay_mongo", lambda: True)
    with ingest_status._lock:
        prev_mem = dict(ingest_status._MEM)
        ingest_status._MEM.clear()
        ingest_status._MEM.update({"cycle_id": None, "phase": "idle", "ready": True, "updated_ms": None})
    with ingest_status._view_lock:
        ingest_status._mongo_view.clear()
        ingest_status._mongo_view.update({"cycle_id": "old", "phase": "ready"})
        ingest_status._mongo_view_at = time.time() - 60  # stale cached doc
    try:
        with patch("app.store.ingest_status.sat_mongo.col", return_value=SlowCol()):
            c = TestClient(app)
            t0 = time.monotonic()
            r = c.get("/api/ready")
            dt = time.monotonic() - t0
        assert r.status_code == 200
        assert dt < 1.0, dt
        assert r.json()["ingest"]["cycle_id"] == "old"
    finally:
        with ingest_status._lock:
            ingest_status._MEM.clear()
            ingest_status._MEM.update(prev_mem)
        with ingest_status._view_lock:
            ingest_status._mongo_view.clear()


def test_pack_or_status_stale_uses_saved_at_projection():
    from app.ingest import kick

    with (
        patch("app.store.shared_packs.storm_saved_at", return_value=time.time() - 60),
        patch("app.store.shared_packs.load_storm", side_effect=AssertionError("full pack read")),
        patch("app.store.ingest_status.snapshot", return_value={"stale": False}),
    ):
        assert kick.pack_or_status_stale() is False
    with patch("app.store.shared_packs.storm_saved_at", return_value=None):
        assert kick.pack_or_status_stale() is True


# ---------------------------------------------------------------- 2. ingest memory


def _rgb_frame(h=600, w=560):
    rng = np.random.default_rng(1)
    rgb = rng.integers(60, 200, size=(h, w, 1), dtype=np.uint8).repeat(3, axis=2)
    rgb[100:103, :, :] = 250  # graticule row
    rgb[:, 200:202, :] = 250  # graticule col
    rgb[300:320, 300:340, 0] = 255  # coloured border blob
    return rgb


def _old_overlay_mask(rgb):
    a = rgb.astype(np.int16)
    chroma = a.max(axis=2) - a.min(axis=2)
    mask = chroma > 40
    gray = a.mean(axis=2)
    d_row = np.abs(gray[1:-1] - 0.5 * (gray[:-2] + gray[2:])) > 25
    d_col = np.abs(gray[:, 1:-1] - 0.5 * (gray[:, :-2] + gray[:, 2:])) > 25
    rows = np.nonzero(d_row.mean(axis=1) > 0.18)[0] + 1
    cols = np.nonzero(d_col.mean(axis=0) > 0.18)[0] + 1
    for r in rows:
        mask[max(0, r - 1) : r + 2, :] = True
    for c in cols:
        mask[:, max(0, c - 1) : c + 2] = True
    grown = mask.copy()
    grown[1:] |= mask[:-1]
    grown[:-1] |= mask[1:]
    grown[:, 1:] |= mask[:, :-1]
    grown[:, :-1] |= mask[:, 1:]
    return grown


def test_overlay_mask_matches_previous_output():
    from app.providers.imd_insat import _luma, _overlay_mask

    rgb = _rgb_frame()
    assert np.array_equal(_overlay_mask(rgb), _old_overlay_mask(rgb))
    ref = rgb.astype(np.float32) @ np.array([0.299, 0.587, 0.114], dtype=np.float32)
    assert np.allclose(_luma(rgb), ref, atol=1e-3)


def _hem_file(path: Path, h=400, w=380):
    h5py = pytest.importorskip("h5py")
    la = np.linspace(45, -10, h, dtype=np.float32)[:, None] * np.ones((1, w), np.float32)
    lo = np.linspace(40, 110, w, dtype=np.float32)[None, :] * np.ones((h, 1), np.float32)
    hem = (np.arange(h * w, dtype=np.int32).reshape(1, h, w) % 3000).astype(np.int16)
    hem[0, ::9, ::7] = -999
    with h5py.File(path, "w") as f:
        d = f.create_dataset("HEM", data=hem)
        d.attrs["_FillValue"] = np.int16(-999)
        d.attrs["scale_factor"] = np.float32(0.01)
        a = f.create_dataset("Latitude", data=(la * 100).astype(np.int16))
        a.attrs["scale_factor"] = np.float32(0.01)
        b = f.create_dataset("Longitude", data=(lo * 100).astype(np.int16))
        b.attrs["scale_factor"] = np.float32(0.01)
    return la, lo, hem


def test_sample_h5_point_matches_full_read(tmp_path):
    from app.providers.mosdac import _sample_h5

    p = tmp_path / "3SIMG_L2B_HEM.h5"
    la, lo, hem = _hem_file(p)
    for lat, lon in ((22.07, 88.07), (10.0, 75.3), (30.5, 95.1)):
        got = _sample_h5(p, lat, lon)
        # brute-force reference on the stride-8 rule the sampler uses
        step = 8
        sub = (la[::step, ::step] - lat) ** 2 + (lo[::step, ::step] - lon) ** 2
        yi, xi = np.unravel_index(np.nanargmin(sub), sub.shape)
        y0, x0 = yi * step, xi * step
        d = (la[y0 : y0 + step, x0 : x0 + step] - lat) ** 2 + (lo[y0 : y0 + step, x0 : x0 + step] - lon) ** 2
        py, px = np.unravel_index(np.nanargmin(d), d.shape)
        raw = int(hem[0, y0 + py, x0 + px])
        want = 0.0 if raw == -999 else raw * 0.01
        if want > 200:
            assert got is None
        else:
            assert got == pytest.approx(want, abs=1e-3)


def test_release_memory_is_safe():
    from app.ingest.cycle import release_memory

    out = release_memory()
    assert "gc" in out


# ---------------------------------------------------------------- 3b. event-loop CPU


def _old_advect(grid, u, v):
    from app.science.rain_field import _bilinear

    h, w = len(grid), len(grid[0])
    return [[_bilinear(grid, y - v, x - u) for x in range(w)] for y in range(h)]


def test_vectorised_advect_matches_bilinear_loop():
    import random

    from app.science.rain_field import advect

    rnd = random.Random(7)
    for _ in range(60):
        h, w = rnd.randint(1, 18), rnd.randint(1, 18)
        g = [[rnd.random() * 10 for _ in range(w)] for _ in range(h)]
        u, v = rnd.uniform(-4, 4), rnd.uniform(-4, 4)
        got, want = advect(g, u, v), _old_advect(g, u, v)
        assert np.allclose(np.array(got), np.array(want), atol=1e-12)


def test_pn_status_does_not_import_heavy_modules(monkeypatch):
    import subprocess
    import sys

    code = (
        "import sys, os; os.environ['PN_ENABLED']='0'; os.environ['CLOUD_LIGHT']='1';"
        "from app.science import pn; pn.status();"
        "from app.science.pn import v7, net, correct; v7.status(); net.status(); correct.status();"
        "bad=[m for m in ('onnxruntime','cv2','scipy','eccodes') if m in sys.modules];"
        "print(bad); sys.exit(1 if bad else 0)"
    )
    r = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, cwd=str(Path(__file__).resolve().parents[1]))
    assert r.returncode == 0, r.stdout + r.stderr

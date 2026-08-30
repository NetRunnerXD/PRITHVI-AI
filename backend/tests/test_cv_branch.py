from app.ml.vera.cv_branch import persist_grid, run


def test_cv_forward_derived_keys(tmp_path, monkeypatch):
    from app.ml.vera import cv_branch

    monkeypatch.setattr(cv_branch, "FRAME_DIR", tmp_path)
    monkeypatch.setattr(cv_branch, "SEQ_PATH", tmp_path / "seq.json")
    grid = [[240.0] * 16 for _ in range(16)]
    grid[4][4] = 210.0
    persist_grid(grid, "https://example/ir.jpg")
    persist_grid([[230.0] * 16 for _ in range(16)], "https://example/ir.jpg")
    pack = run({"ok": True, "insat": {"ok": True, "url": "https://example/ir.jpg"}, "cells": []})
    d = pack["derived"]
    for k in ("cloud_top_temp_k", "ctt_trend_k", "convective_initiation", "precip_est_mmh", "amv_dx"):
        assert k in d
    assert pack["stage1_cnn"]["shape"][1] == 512
    assert pack["frames"]
    assert len(pack["embedding"]) == 32


def test_cv_empty():
    pack = run({})
    assert "stage1_cnn" in pack
    assert pack["embedding"]


def test_crop_chrome_shrinks():
    from PIL import Image
    import io
    from app.providers.imd_insat import crop_chrome

    im = Image.new("RGB", (200, 200), (10, 20, 30))
    buf = io.BytesIO()
    im.save(buf, format="JPEG")
    out = crop_chrome(buf.getvalue())
    im2 = Image.open(io.BytesIO(out))
    assert im2.size[0] < 200 and im2.size[1] < 200


def test_asia_bounds_asiamer():
    from app.providers.imd_insat import ASIA_BOUNDS

    west, east, south, north = ASIA_BOUNDS
    assert west == 40.0 and east == 110.0
    assert south == -10.0 and north == 45.0


def test_rain_png_from_grid():
    from app.ml.vera.cv_branch import rain_png

    g = [[250.0] * 8 for _ in range(8)]
    g[2][2] = 210.0
    uri = rain_png(g, size=16)
    assert uri and uri.startswith("data:image/png;base64,")

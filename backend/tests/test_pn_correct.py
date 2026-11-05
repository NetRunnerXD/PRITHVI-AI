"""PN-Correct v6 (separate 'rain within 25 km' layer, 6/9/12 h): flag off by default, feature builder parity with
research reference_feature_builder_v6.one(), ONNX vs torch, latency rule, and that the v7 field is never altered.
Heavy checks skip when the git-ignored model or the research data are absent."""

from __future__ import annotations

import asyncio
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import pytest

from app.science.pn import correct, hooks, nwp_v7

UTC = timezone.utc
MODEL = Path(correct.model_path())
REF = Path(os.environ.get("PN_CORRECT_RESEARCH", "/workspace/prithvi-nowcast/export_v7_app/pn_correct"))
DATA = Path(os.environ.get("PRITHVI_DATA", "/workspace/prithvi-nowcast/data_nowcast"))
CKPT = Path("/workspace/nwpc_v6/runs_v6/nwpc_best.pt")


def _ref():
    if not (REF / "reference_feature_builder_v6.py").exists() or not (DATA / "gfs").exists():
        pytest.skip("research reference builder / data_nowcast not on this machine")
    sys.path.insert(0, str(REF))
    import reference_feature_builder_v6 as R

    return R


def test_flag_off_by_default_and_judge_never_wired(monkeypatch):
    monkeypatch.delenv("PN_CORRECT_ENABLED", raising=False)
    assert not hooks.correct_enabled() and hooks.correct({"t_issue": datetime(2026, 10, 20, 14)}) is None
    monkeypatch.setenv("PN_JUDGE_ENABLED", "1")
    assert hooks.judge({}) is None  # PN-Judge failed its pre-registered test → not wired
    for L in range(1, 13):
        assert hooks.handover_weight(L, True) == 1.0 and hooks.handover_weight(L, False) == 1.0
    st = hooks.status()
    assert st["pn_judge"]["wired"] is False and st["handover_weight"] == 1.0


def test_params_match_research_export():
    import json

    c = correct.cfg()
    assert c["cut"] == {"6": 0.30, "9": 0.28, "12": 0.26} and c["leads_h"] == [6, 9, 12]
    assert len(c["channels"]) == 34 and c["missing_flag_channels"] == [0, 11, 22, 25, 27]
    for ch, lh in zip(c["channels"], c["lohi"]):
        assert np.allclose(correct.lohi(ch), lh, atol=1e-6)
    p = REF / "pn_correct_params.json"
    if p.exists():
        P = json.load(open(p))
        assert P["channels"] == c["channels"] and P["temperatures"] == c["temperatures"]


def test_features_all_missing_and_static():
    T = datetime(2026, 10, 20, 14)
    X = correct.features(T, None, nwp_v7.runs_gfs(T)[0], None, nwp_v7.runs_ifs(T)[0], [None] * 3)
    ch = correct.cfg()["channels"]
    assert X.shape == (34, 133, 141) and X.dtype == np.uint8
    for c in ("gfs_r6", "gfs_cape", "ifs_r12", "ifs_shear", "obs_r1", "tir_mean", "sat_id"):
        assert (X[ch.index(c)] == 255).all()
    for c in ("gfs_ok", "ifs_ok", "sat_ok"):
        assert (X[ch.index(c)] == 0).all()
    assert X[ch.index("lat")][0, 0] == 254 and X[ch.index("lon")][0, 0] == 0  # row 0 = 38 N, col 0 = 65 E
    # an IMERG hour with ≤ 90 % finite pixels is treated as missing (imerg_hour() rule)
    r = np.full((331, 351), np.nan, np.float32); r[:100] = 2.0
    X = correct.features(T, None, nwp_v7.runs_gfs(T)[0], None, nwp_v7.runs_ifs(T)[0], [r, None, None])
    assert (X[ch.index("obs_r1")] == 255).all()


def test_correct_runs_respect_latency_rule():
    T = datetime(2025, 1, 20, 14)  # a run no other test caches
    seen: list[str] = []

    async def get(url, rng):
        seen.append(url); return None

    out = asyncio.run(nwp_v7.build_correct_runs(T, get))
    assert out["gfs_run"] == datetime(2025, 1, 20, 6) and out["ifs_run"] == datetime(2025, 1, 20, 0)
    gfs = [u for u in seen if "gfs" in u]
    assert gfs and all("gfs.t06z" in u and "gfs.20250120" in u for u in gfs)
    assert [u for u in seen if "/ifs/" in u] and all("20250120/00z" in u for u in seen if "/ifs/" in u)
    for t in (datetime(2026, 10, 20, h) for h in range(24)):
        assert set(nwp_v7.correct_steps_ifs(t)) <= set(nwp_v7.IFS_V6_STEPS)
        assert (t - nwp_v7.runs_gfs(t)[0]) >= timedelta(hours=6) and (t - nwp_v7.runs_ifs(t)[0]) >= timedelta(hours=8)


def test_live_builder_matches_reference_on_stored_samples():
    R = _ref()
    ts = [t for t in R.times() if t >= datetime(2026, 9, 1)][::37][:8]
    n = 0
    for T in ts:
        r = R.one(T)
        if r is None:
            continue
        g, c = R.gfs_run(T), R.ifs_run(T)
        fg, fx = DATA / f"gfs/{g:%Y%m%d%H}.npz", DATA / f"gfs/{g:%Y%m%d%H}_x.npz"
        zg = None
        if fg.exists() and fx.exists():
            zg = dict(np.load(fg)); zg.update(np.load(fx))
        fi = DATA / f"nwp/ifs_v6/{c:%Y%m%d%H}.npz"
        zi = dict(np.load(fi)) if fi.exists() else None
        obs = [R.imerg_hour(T - timedelta(hours=k + 1)) for k in range(3)]
        t1, sid = R.tir(T - timedelta(hours=1)); t2, _ = R.tir(T - timedelta(hours=2))
        X = correct.features(T, zg, g, zi, c, obs, t1, t2 if t1 is not None else None, sid)
        assert np.array_equal(X, r[1]), T
        n += 1
    assert n >= 4


@pytest.mark.skipif(not MODEL.exists(), reason="pn_correct_v6.onnx not present (git-ignored)")
def test_onnx_layer_shapes_and_cuts(monkeypatch):
    T = datetime(2026, 10, 20, 14)
    inp = {"gfs": {}, "ifs": {}, "gfs_run": nwp_v7.runs_gfs(T)[0], "ifs_run": nwp_v7.runs_ifs(T)[0], "obs": [None] * 3}
    r = correct.run(T, inp)
    assert r["p_rain"].shape == (3, 133, 141) and 0 <= r["p_rain"].min() and r["p_rain"].max() <= 1
    for k, L in enumerate(correct.LEADS):
        assert np.array_equal(r["event"][k], r["p_rain"][k] >= correct.cfg()["cut"][str(L)])
    monkeypatch.setenv("PN_CORRECT_ENABLED", "1")
    lay = hooks.correct({"t_issue": T, "pnc": inp})
    assert lay["ok"] and [x["lead_h"] for x in lay["leads"]] == [6, 9, 12]
    assert lay["leads"][0]["valid_start"].startswith("2026-10-20T19:00")  # hour [T+5, T+6)
    assert lay["leads"][2]["cut"] == 0.26 and lay["inputs"]["gfs"] is False


@pytest.mark.skipif(not MODEL.exists() or not CKPT.exists(), reason="model or research checkpoint absent")
def test_onnx_matches_torch_on_reference_features():
    R = _ref()
    torch = pytest.importorskip("torch")
    sys.path.insert(0, str(REF))
    from pn_correct_model import UNet, Wrapped

    net = UNet(); net.load_state_dict(torch.load(str(CKPT), map_location="cpu"))
    W = Wrapped(net.eval(), correct.cfg()["temperatures"]).eval()
    Xs = [r[1] for r in (R.one(t) for t in (datetime(2026, 9, 10, 2), datetime(2026, 9, 20, 14))) if r is not None]
    x = correct.pack(np.stack(Xs))
    with torch.no_grad():
        pt = W(torch.from_numpy(x))[0].numpy()
    po = correct._session().run(["p_rain"], {"x": x})[0]
    assert np.abs(pt - po).max() < 1e-4


def test_layer_is_separate_and_v7_field_unchanged(monkeypatch):
    from app.science.pn import live

    seen = {}

    def core(obs, nwp, nwp_val, corrected):
        seen["corrected"] = corrected
        return {"ok": True, "status": "ok", "leads": [{"lead_h": L, "nowcast_weight": hooks.handover_weight(L, bool(corrected))} for L in range(1, 13)]}

    lay = {"ok": True, "leads": [{"lead_h": 6, "cells": []}]}
    monkeypatch.setattr(live, "_build_v7_core", core)
    monkeypatch.setattr(hooks, "correct", lambda ctx: lay)
    obs = {"hours": [datetime(2026, 10, 20, 13, tzinfo=UTC)], "rain": [np.zeros((320, 348), np.float32)], "errors": []}
    pk = live._build_v7(obs, None, None, {"gfs_run": datetime(2026, 10, 20, 6)})
    assert pk["pn_correct"] is lay and all(x["nowcast_weight"] == 1.0 for x in pk["leads"])
    pk0 = live._build_v7(obs, None, None, None)
    assert "pn_correct" not in pk0 and pk0["leads"] == pk["leads"]


def test_hours_ext_missing_half_hour_is_none():
    from app.science.pn import live

    h = datetime(2026, 10, 20, 10, tzinfo=UTC)
    out = asyncio.run(live.hours_ext({"hrefs": {h: "x"}}, [h], 331, 351))
    assert out == [None]


def test_cells_pool_to_half_degree():
    ev = np.zeros((133, 141), bool); ev[10, 10] = True; ev[11, 11] = True
    p = np.where(ev, 0.6, 0.1).astype(np.float32)
    c = correct.cells(ev, p)
    assert len(c) == 1 and c[0]["p"] == 0.6 and abs(c[0]["lat"] - (38 - 0.25 * 10.5)) < 1e-6


def test_point_lookup_and_summary(monkeypatch):
    from app import cache
    from app.science import pn

    p = np.zeros((3, 133, 141), np.uint8); i, j = int(round((38 - 22.5) / 0.25)), int(round((88.25 - 65) / 0.25))
    p[0, i, j] = 200; p[2, i, j] = 50  # 0.80 at 6 h (rain), 0.20 at 12 h (< 0.26 cut)
    cache.set("pn7:pnc:last", {"t_issue": datetime(2026, 10, 20, 14), "p": p}, 60)
    pt = correct.point(22.5, 88.25)
    assert pt["leads"]["6"] == {"p": 0.8, "rain": True} and pt["leads"]["12"] == {"p": 0.2, "rain": False}
    assert correct.point(40.0, 88.0) is None  # outside the 0.25° India grid
    monkeypatch.delenv("PN_CORRECT_ENABLED", raising=False)
    assert "pn_correct" not in pn.science_summary(22.5, 88.25)

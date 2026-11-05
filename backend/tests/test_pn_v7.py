"""PRITHVI-Nowcast v7 live path: latency rule, NWP maths, LK parity, ONNX runner, pack honesty,
pn_runs store and endpoints. Heavy checks skip when the (git-ignored) model/bundle are absent."""

from __future__ import annotations

import asyncio
import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import pytest

from app.science.pn import hooks, nwp_v7, v7

UTC = timezone.utc
MODEL = Path(v7.model_path())
BUNDLE = Path(os.environ.get("PN_V7_BUNDLE", "/workspace/v7bundle"))
RESEARCH = Path(os.environ.get("PN_V7_RESEARCH", "/workspace/prithvi-nowcast/gpu_bundle/v7"))


# ---------------------------------------------------------------- latency rule
def test_latency_rule_gfs_6h_ifs_8h():
    t = datetime(2026, 10, 20, 17)
    assert nwp_v7.runs_gfs(t) == [datetime(2026, 10, 20, 6), datetime(2026, 10, 20, 0)]
    assert nwp_v7.runs_ifs(t) == [datetime(2026, 10, 20, 0), datetime(2026, 10, 19, 12)]
    t = datetime(2026, 10, 20, 12)  # exactly 6 h after 06Z → allowed; IFS 12Z−8 h = 04Z → 00Z
    assert nwp_v7.runs_gfs(t)[0] == datetime(2026, 10, 20, 6)
    assert nwp_v7.runs_ifs(t)[0] == datetime(2026, 10, 20, 0)
    for h in range(24):
        t = datetime(2026, 10, 20) + timedelta(hours=h)
        assert (t - nwp_v7.runs_gfs(t)[0]) >= timedelta(hours=6)
        assert (t - nwp_v7.runs_ifs(t)[0]) >= timedelta(hours=8)


# ---------------------------------------------------------------- bundle maths
def _gfs_const(rate_mm_h: float) -> dict[str, np.ndarray]:
    a = lambda h: np.full((133, 141), rate_mm_h * h, np.float32)  # noqa: E731
    z = {"APCP_f003": a(3), "APCP_f006": a(6)}
    for f in (9, 15, 21):
        z[f"APCP_f{f:03d}"] = a(3)  # 6-9 / 12-15 / 18-21 buckets
    for f in (12, 18, 24):
        z[f"APCP_f{f:03d}"] = a(6)  # 6-12 / 12-18 / 18-24 buckets
    return z


def test_gfs_windows_constant_rate_and_age():
    t = datetime(2026, 10, 20, 17)
    runs = {datetime(2026, 10, 20, 6): _gfs_const(2.0)}
    w, age, used = nwp_v7.windows(t, "gfs", runs)
    assert w is not None and age == 11.0 and used == [datetime(2026, 10, 20, 6)]
    for k in range(4):
        assert w[k].shape == (80, 87) and np.allclose(w[k], 2.0)


def test_gfs_windows_missing_bucket_masks_group():
    t = datetime(2026, 10, 20, 17)
    z = _gfs_const(1.0); z.pop("APCP_f024"); z.pop("APCP_f021")
    w, _, _ = nwp_v7.windows(t, "gfs", {datetime(2026, 10, 20, 6): z})
    assert w is None  # window 9-12 h (20.5..22.5 h) cannot be formed → GFS group masked


def test_ifs_windows_and_steps_needed():
    t = datetime(2026, 10, 20, 17)  # IFS 00Z, age 17 h
    st = nwp_v7._steps_needed(17, nwp_v7.IFS_TP_STEPS)
    assert st[0] == 15 and st[-1] == 30
    z = {f"tp_{s:03d}": np.full((133, 141), 0.5 * s, np.float32) for s in st}
    w, age, _ = nwp_v7.windows(t, "ifs", {datetime(2026, 10, 20, 0): z})
    assert age == 17.0 and all(np.allclose(x, 0.5) for x in w)


def test_split_grib():
    def msg(n):
        body = b"GRIB" + b"\0\0\0" + b"\x02" + n.to_bytes(8, "big")
        return body + b"x" * (n - len(body))

    blob = msg(40) + msg(64)
    parts = nwp_v7.split_grib(blob)
    assert [len(p) for p in parts] == [40, 64]


def test_build_masks_everything_when_fetch_fails():
    async def nothing(url, rng):
        return None

    out = asyncio.run(nwp_v7.build(datetime(2026, 10, 20, 17), v7.cfg()["norm_nenv"], get=nothing))
    assert out["nm"].tolist() == [0, 0] and out["em"].tolist() == [0, 0]
    g = v7.groups(out)
    assert g["imerg"] and not any(g[k] for k in ("insat", "gfs_rain", "ifs_rain", "gfs_env", "ifs_env"))


def test_quantise_matches_bundle_formula():
    mm = np.array([[[0.0, 0.5, 1.0, 20.0, -3.0, np.nan]]], np.float32)
    q = v7.quantise(mm)
    ref = np.clip(np.round(np.log1p(np.nan_to_num(np.maximum(mm, 0))) / 0.02), 0, 255).astype(np.uint8) * np.float32(0.02)
    assert np.array_equal(q, ref)
    assert q[0, 0, 2] > v7.THR and not q[0, 0, 1] > v7.THR  # 1 mm/h → q=35 → event; 0.5 mm/h → no event
    hr = v7.hour_feats(datetime(2026, 10, 20, 6), np.array([12.0, 24.0]))
    assert hr.shape == (1, 6) and abs(hr[0, 0] - 1.0) < 1e-6 and abs(hr[0, 4] - 0.5) < 1e-6


# ---------------------------------------------------------------- motion
def _blob_frames():
    yy, xx = np.mgrid[0:320, 0:348]
    fr = []
    for k in range(4):
        cy, cx = 150 + 2 * k, 160 + 3 * k
        fr.append(8.0 * np.exp(-(((yy - cy) / 18.0) ** 2 + ((xx - cx) / 25.0) ** 2)) + 3.0 * np.exp(-(((yy - 60 - k) / 10.0) ** 2 + ((xx - 250 + 2 * k) / 12.0) ** 2)))
    return np.stack(fr).astype(np.float32)


def test_lk_vendored_matches_pysteps():
    pytest.importorskip("cv2")
    try:
        from pysteps import motion
    except Exception:  # noqa: BLE001
        pytest.skip("pysteps not installed (only needed for this parity check)")
    from app.science.pn.lk import dense_lucaskanade

    rr = _blob_frames()
    a = dense_lucaskanade(rr, buffer_mask=5)
    b = motion.get_method("LK")(rr, fd_kwargs=dict(buffer_mask=5), verbose=False)
    assert np.array_equal(a, b)


def test_lk_matches_bundle_motion():
    pytest.importorskip("cv2")
    if not (BUNDLE / "motion.npy").exists():
        pytest.skip("research bundle not on this machine")
    R = np.load(BUNDLE / "rain.npy", mmap_mode="r"); M = np.load(BUNDLE / "motion.npy", mmap_mode="r"); T = list(np.load(BUNDLE / "times.npy"))
    i = T.index("2026091512")
    m = v7.motion_lk(R[i - 6:i].astype(np.float32) * 0.02)
    assert np.array_equal(m, M[i].astype(np.float32))


# ---------------------------------------------------------------- ONNX runner
needs_model = pytest.mark.skipif(not MODEL.exists(), reason="v7 ONNX not exported on this machine")


@needs_model
def test_v7_run_shapes_and_thresholds():
    pytest.importorskip("onnxruntime")
    rain = np.zeros((6, 320, 348), np.float32); rain[:, 100:140, 100:150] = 6.0
    r = v7.run(rain, datetime(2026, 10, 20, 17, tzinfo=UTC), None)
    assert r["ok"] and r["p_rain"].shape == (12, 320, 348) and r["rain_event_0p5"].shape == (12, 64, 69)
    assert r["groups"]["gfs_rain"] is False and r["groups"]["insat"] is False
    cut = np.array(v7.cfg()["ops_blend"]["0.1"]["csi"])[:, None, None]
    assert np.array_equal(r["rain_event"], r["p_rain"] >= cut)
    assert r["rain_event"][0][100:140, 100:150].mean() > 0.5  # an observed rain area persists at lead 1


@needs_model
def test_v7_onnx_matches_research_on_real_samples():
    pytest.importorskip("onnxruntime")
    pytest.importorskip("torch")
    if not (BUNDLE / "rain.npy").exists() or not (RESEARCH / "train_v7.py").exists():
        pytest.skip("research bundle/scripts not on this machine")
    import sys

    import torch

    sys.path.insert(0, str(RESEARCH))
    import train_v7 as TV

    Z = TV.load_bundle(str(BUNDLE), mmap="r"); S, T, tt = TV.samples(Z, False)
    st = torch.from_numpy(Z["static"].astype(np.float32))[None].clone(); st[:, 0] /= 2.0
    net = TV.Net(st, "v7"); net.load_state_dict(torch.load("/workspace/v7runs/r2/best.pt", map_location="cpu", weights_only=True)); net.eval()
    sess = v7._session(); names = ["x", "sat", "sm", "env", "em", "nwp", "nm", "mo", "hr"]
    for i in S["test"][::400][:3]:
        x, _ = TV.make_batch(Z, tt, [i], "v7", "cpu")
        with torch.no_grad():
            _, lg = net(*x)
        o = sess.run(None, {k: v.numpy() for k, v in zip(names, x)})
        assert float(np.abs(o[1][0] - torch.sigmoid(lg).numpy()[0]).max()) < 5e-4


# ---------------------------------------------------------------- live pack honesty + pn_runs
@pytest.fixture()
def runs_file(tmp_path, monkeypatch):
    from app.store import pn_runs

    monkeypatch.setenv("PN_RUNS_FILE", str(tmp_path / "pn_runs.json"))
    pn_runs._reset_for_tests()
    yield tmp_path / "pn_runs.json"
    pn_runs._reset_for_tests()


def _obs(n, end, gap=False):
    hours = [end - timedelta(hours=n - 1 - k) for k in range(n)]
    if gap:
        hours = hours[:2] + hours[3:]
    rain = [np.zeros((320, 348), np.float32) for _ in hours]
    for r in rain:
        r[50:60, 50:60] = 4.0
    return {"hours": hours, "rain": rain, "errors": []}


def test_build_v7_gap_falls_back_to_persistence(runs_file):
    from app.science.pn import live

    end = datetime.now(UTC).replace(minute=0, second=0, microsecond=0) - timedelta(hours=3)
    pk = live._build_v7(_obs(7, end, gap=True), None, None)
    assert pk["ok"] and pk["status"] == "persistence_fallback" and pk["persistence_cells"]
    from app.store import pn_runs

    docs = pn_runs.recent(1)
    assert docs and docs[-1]["status"] == "persistence_fallback"


def test_build_v7_stale_imerg_is_persistence(runs_file):
    from app.science.pn import live

    end = datetime.now(UTC).replace(minute=0, second=0, microsecond=0) - timedelta(hours=20)
    pk = live._build_v7(_obs(9, end), None, None)
    assert pk["status"] == "persistence_fallback" and "v7 not run" in pk["note"]


def test_build_v7_model_path_records_and_verifies(runs_file, monkeypatch):
    from app import cache
    from app.science.pn import live
    from app.store import pn_runs

    def fake_run(rain6, t_issue, nwp=None):
        ev = np.zeros((12, 320, 348), bool); ev[:, 50:60, 50:60] = True
        p = ev.astype(np.float32) * 0.9
        return {"ok": True, "mm_h": p * 5, "p_net": p, "p_rain": p, "rain_event": ev, "rain_event_0p5": v7.pool(ev), "p_0p5": v7.pool(p),
                "groups": {"imerg": True, "insat": False, "gfs_rain": True, "ifs_rain": False, "gfs_env": True, "ifs_env": False},
                "nwp_runs": {"gfs": ["2026-10-20T06Z"], "ifs": []}, "nwp_age_h": [11.0, 0.0]}

    monkeypatch.setattr(v7, "run", fake_run)
    cache.set("pn7:fc:index", {}, 60)
    end = datetime.now(UTC).replace(minute=0, second=0, microsecond=0) - timedelta(hours=3)
    pk = live._build_v7(_obs(9, end - timedelta(hours=2)), None, None)  # run issued 2 h before the newest hours
    assert pk["status"] == "ok" and pk["groups_masked"] == ["insat", "ifs_rain", "ifs_env"]
    assert pk["test_csi"]["1"] == 0.643 and len(pk["leads"]) == 12 and pk["validation"]["by_lead"]
    # two newer hours arrive → leads 1..2 of that run get verified (perfect forecast here)
    live._build_v7(_obs(9, end), None, None)
    d = [x for x in pn_runs.recent(1) if x["run_id"] == pk["run_id"]][0]
    assert set(d["verif"]) >= {"1", "2"} and d["verif"]["1"]["csi"] == 1.0
    assert d["nwp"]["gfs"] == ["2026-10-20T06Z"] and d["groups"]["gfs_rain"] is True
    assert len(json.dumps(d)) < 2048
    tr = pn_runs.track(1, "v7")
    assert tr["leads"]["1"]["csi"] == 1.0 and tr["n_runs"] >= 1


def test_pn_runs_doc_size_full_verification(runs_file):
    from app.store import pn_runs

    pn_runs.upsert_run({"run_id": "v7-2026102017", "version": "v7", "t_issue_ms": 1_792_000_000_000, "run_at_ms": 1_792_000_100_000, "status": "model",
                        "groups": {k: True for k in ("imerg", "insat", "gfs_rain", "ifs_rain", "gfs_env", "ifs_env")},
                        "nwp": {"gfs": ["2026-10-20T06Z", "2026-10-20T00Z"], "ifs": ["2026-10-20T00Z"], "gfs_env": "2026-10-20T06Z", "ifs_env": "2026-10-20T00Z"}})
    for L in range(1, 13):
        pn_runs.add_verification("v7-2026102017", L, {**pn_runs.scores(123456, 23456, 34567), "pc": 0.456})
    d = pn_runs._MEM["v7-2026102017"]
    assert len(json.dumps(d)) < 2048
    pn_runs._reset_for_tests()
    assert pn_runs.verified_leads("v7-2026102017") == set(range(1, 13))  # reloaded from disk


def test_pn_runs_uses_mongo_when_available(runs_file, monkeypatch):
    from app.store import pn_runs, sat_mongo

    calls = []

    class Col:
        def create_index(self, *a, **k): calls.append(("index", a))
        def update_one(self, q, u, upsert=False): calls.append(("update", q["_id"], sorted(u), upsert))
        def find(self, *a, **k): raise RuntimeError("down")

    monkeypatch.setattr(sat_mongo, "col", lambda name: Col() if name == "pn_runs" else None)
    pn_runs.upsert_run({"run_id": "v7-x", "version": "v7", "t_issue_ms": int(datetime.now(UTC).timestamp() * 1000), "status": "model"})
    pn_runs.add_verification("v7-x", 1, pn_runs.scores(1, 0, 0))
    assert ("index", ("t_issue_ms",)) in calls
    assert ("update", "v7-x", ["$set", "$setOnInsert"], True) in calls
    assert any(c[0] == "update" and c[2] == ["$set"] for c in calls)
    assert pn_runs.recent(1)  # Mongo read fails → memory/disk


def test_pn_runs_silent_when_mongo_raises(runs_file, monkeypatch):
    from app.store import pn_runs, sat_mongo

    def boom(name):
        raise RuntimeError("no cluster")

    monkeypatch.setattr(sat_mongo, "col", boom)
    pn_runs.upsert_run({"run_id": "v7-y", "version": "v7", "t_issue_ms": 1, "status": "model"})
    pn_runs.add_verification("v7-y", 3, pn_runs.scores(0, 1, 1))
    assert pn_runs.verified_leads("v7-y") == {3}


# ---------------------------------------------------------------- flags, hooks, endpoints
def test_hooks_off_by_default(monkeypatch):
    monkeypatch.delenv("PN_JUDGE_ENABLED", raising=False); monkeypatch.delenv("PN_CORRECT_ENABLED", raising=False)
    assert hooks.judge({}) is None and hooks.correct({}) is None and hooks.handover_weight(5, False) == 1.0
    monkeypatch.setenv("PN_JUDGE_ENABLED", "1")
    assert hooks.judge_enabled() and hooks.judge({}) is None  # flag on but no model → still a no-op


def test_engine_selection(monkeypatch):
    from app.science.pn import live

    monkeypatch.setenv("PN_ENABLED", "1")
    monkeypatch.setenv("PN_VERSION", "v7")
    assert live._ck() == live.CK7 and live.engine_status()["version"] == "v7"
    monkeypatch.setenv("PN_VERSION", "v4")
    assert live._ck() == live.CK and "version" not in live.engine_status()
    monkeypatch.delenv("PN_ENABLED")
    monkeypatch.setenv("PN_VERSION", "v7")
    assert live.engine_status()["enabled"] is False and live.peek(kick=False) is None


def test_endpoints_track_and_status(runs_file, monkeypatch):
    from fastapi.testclient import TestClient

    from app.main import app

    monkeypatch.delenv("PN_ENABLED", raising=False)
    c = TestClient(app)
    r = c.get("/api/research/pn-track", params={"days": 30})
    assert r.status_code == 200 and r.json()["test_csi"]["12"] == 0.364
    r = c.get("/api/research/pn-live")
    assert r.status_code == 200 and r.json()["status"] == "disabled"
    s = c.get("/api/research/status").json()
    assert "pn_nowcast_v7" in s and s["hooks"]["pn_judge"]["flag"] is False


def test_science_summary_has_test_scores(monkeypatch):
    from app.science import pn

    monkeypatch.delenv("PN_ENABLED", raising=False)
    s = pn.science_summary()
    assert s["test_csi"] == {"1": 0.643, "3": 0.466, "6": 0.393, "12": 0.364} and s["enabled"] is False

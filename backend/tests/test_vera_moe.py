from app.ml.vera.fusion import mixture_pdf, schaake_shuffle
from app.ml.vera.gate import kalman_smooth, tv_smooth
from app.ml.vera.pipeline import build_vera
from app.ml.vera.temporal import sat_weight
from app.schemas.location import Location


def test_gate_sums_to_one():
    sm = kalman_smooth({"a": 0.5, "b": 0.5}, {"a": 0.9, "b": 0.1})
    assert abs(sum(sm.values()) - 1.0) < 1e-6


def test_kalman_smoothness():
    prev = {"a": 0.5, "b": 0.5}
    curr = {"a": 1.0, "b": 0.0}
    sm = kalman_smooth(prev, curr)
    assert sm["a"] < 0.95
    assert sm["a"] > 0.5


def test_tv_smooth_shape():
    g = [[[1.0, 0.0, 0.0] for _ in range(3)] for _ in range(3)]
    g[0][0] = [0.0, 1.0, 0.0]
    out = tv_smooth(g)
    assert len(out) == 3 and len(out[0][0]) == 3


def test_mixture_pdf_positive():
    xs = [i for i in range(0, 40)]
    y = mixture_pdf([(10.0, 3.0), (20.0, 4.0)], [0.5, 0.5], [float(x) for x in xs])
    assert all(v >= 0 for v in y)
    assert sum(y) > 0


def test_schaake_permutation():
    traces = [[3.0, 1.0], [1.0, 4.0]]
    hist = [[10.0, 2.0], [1.0, 9.0]]
    out = schaake_shuffle(traces, hist)
    assert sorted(out[i][0] for i in range(2)) == sorted(t[0] for t in traces)


def test_sat_weight_schedule():
    assert sat_weight(1) >= 0.69
    assert sat_weight(24) <= 0.25
    assert sat_weight(100) <= 0.06


def test_build_vera_graph():
    loc = Location(
        id="x",
        label="Howrah",
        country="IN",
        state="West Bengal",
        district="Howrah",
        lat=22.6,
        lon=88.3,
        timezone="Asia/Kolkata",
        crop_hint="rice",
    )
    f = {
        "precip_days": [12.0, 4.0],
        "precip_3d_mm": 16.0,
        "precip_z": 0.8,
        "clim_daily_mm": 7.0,
        "daily_times": ["2026-08-20"],
        "members": {"ecmwf_ifs025": {"precip_days": [10.0, 5.0]}, "gfs_seamless": {"precip_days": [14.0, 3.0]}},
        "hourly_precip": [0.2] * 12,
    }
    pack = build_vera(f, loc, {"ok": True, "cells": [], "insat": {"ok": True, "url": "https://example/ir.jpg"}}, f["members"])


def test_build_vera_short_daily_times():
    loc = Location(
        id="x",
        label="Haldia",
        country="IN",
        state="West Bengal",
        district="Purba Medinipur",
        lat=22.07,
        lon=88.07,
        timezone="Asia/Kolkata",
        crop_hint="rice",
    )
    f = {
        "precip_days": [12.0, 4.0],
        "precip_3d_mm": 16.0,
        "precip_z": 0.8,
        "clim_daily_mm": 7.0,
        "daily_times": ["2026-08-20"],
        "members": {
            "ecmwf_ifs025": {"precip_days": [10.0, 5.0], "daily_times": ["2026-08-20"]},
            "gfs_seamless": {"precip_days": [14.0], "daily_times": ["2026-08-20"]},
        },
        "hourly_precip": [0.2] * 12,
    }
    pack = build_vera(f, loc, {"ok": True, "cells": []}, f["members"])
    days = (pack.get("compare") or {}).get("days") or []
    assert len(days) == 7
    assert days[0]["date"] == "2026-08-20"
    assert days[1]["date"] is None
    assert pack["name"] == "VERA-MoE"
    assert pack["graph"]["nodes"]
    assert pack["fusion"]["q50"] is not None
    assert abs(sum(pack["gate"]["weights"].values()) - 1.0) < 1e-3
    assert pack["fusion"].get("q25") is not None
    assert pack.get("api_needed")
    assert len(pack["temporal"]["hourly_0_48"]) == 48
    assert pack["historical"]["embedding_shape"][-1] == 64

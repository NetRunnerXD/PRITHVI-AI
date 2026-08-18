from datetime import datetime, timedelta
from types import SimpleNamespace

from app.providers import sat_obs
from app.science import sat_kalman as sk
from app.science.nowcast import IST, build


def _loc():
    return SimpleNamespace(
        district="Purba Medinipur",
        lat=22.067,
        lon=88.070,
        place_kind="city",
        place_name="Haldia",
    )


def _knots(rates: list[float], t0: datetime | None = None) -> list[dict]:
    t0 = t0 or datetime(2026, 8, 18, 8, 0, tzinfo=IST)
    out = []
    for i, r in enumerate(rates):
        t = t0 + timedelta(hours=i)
        out.append({"t": t.isoformat(timespec="seconds"), "mm": r, "mm_h": r})
    return out


def test_om_never_labelled_satellite():
    times = [f"2026-08-18T{h:02d}:00" for h in range(8, 16)]
    mm = [0.0, 0.4, 1.2, 3.0, 2.1, 0.8, 0.2, 0.0]
    obs = sat_obs.from_open_meteo_hours(times, mm, past_only=True, now_iso="2026-08-18T12:05:00")
    assert obs["source"] == "om-analysis"
    assert obs["source_kind"] == "model-analysis"
    assert "insat" not in obs["source"].lower()
    assert "not insat" in obs["note"].lower() or "not INSAT" in obs["note"]
    # future hours after 12:05 dropped
    assert all("T13" not in k["t"] and "T14" not in k["t"] and "T15" not in k["t"] for k in obs["knots"])
    src = sat_obs.available_source()
    if src["source"] == "om-analysis":
        assert src["source_kind"] == "model-analysis"


def test_causal_predict_does_not_see_next_obs(tmp_path, monkeypatch):
    monkeypatch.setattr(sk, "STATE_PATH", tmp_path / "k.json")
    loc = _loc()
    key = sk.place_key(loc)
    knots = _knots([1.0, 5.0, 5.0])
    st = sk.ingest_knots(key, knots[:1], source="om-analysis", source_kind="model-analysis", reset=True)
    pred = sk.predict_rate(st, 3600.0)
    # Held-out 5 mm/h must not already be the prediction.
    assert pred < 3.0
    st2 = sk.ingest_knots(key, knots[:2], source="om-analysis", source_kind="model-analysis")
    assert st2["last_obs_mm_h"] == 5.0
    assert st2["last_pred_mm_h"] == round(pred, 3) or abs(st2["last_pred_mm_h"] - pred) < 0.05
    assert st2["last_y"] is not None


def test_error_shrinks_after_repeated_obs(tmp_path, monkeypatch):
    monkeypatch.setattr(sk, "STATE_PATH", tmp_path / "k.json")
    loc = _loc()
    key = sk.place_key(loc)
    knots = _knots([0.4, 4.0, 4.1, 3.9, 4.0, 4.05])
    st = sk.ingest_knots(key, knots, source="om-analysis", source_kind="model-analysis", reset=True)
    ys = [abs(float(row["y"])) for row in st["innovations"]]
    assert len(ys) == 6
    # First jump 0.4 → 4 is the hard one; later |y| around 4 mm/h should be smaller.
    assert ys[-1] < ys[1]
    assert abs(sk.predict_rate(st, 0.0) - 4.0) < 1.5
    assert st["n"] == 6
    assert st["mae"] < ys[1]


def test_stride_integrals_match(tmp_path, monkeypatch):
    monkeypatch.setattr(sk, "STATE_PATH", tmp_path / "k.json")
    loc = _loc()
    key = sk.place_key(loc)
    st = sk.ingest_knots(
        key,
        _knots([2.0, 2.1]),
        source="om-analysis",
        source_kind="model-analysis",
        reset=True,
    )
    i1 = sk.integral_mm(st, 60, 1)
    i60 = sk.integral_mm(st, 60, 60)
    assert abs(i1 - i60) < 0.05


def test_locked_hours_unchanged(monkeypatch, tmp_path):
    monkeypatch.setattr(sk, "STATE_PATH", tmp_path / "k.json")
    from app.science import nowcast as nc

    monkeypatch.setattr(nc, "_now", lambda: datetime(2026, 8, 18, 12, 5, tzinfo=nc.IST))
    f = {
        "hourly_times": [f"2026-08-18T{h:02d}:00" for h in range(10, 20)],
        "hourly_precip": [0.0, 0.2, 1.4, 3.2, 2.1, 0.8, 0.3, 0.1, 0.0, 0.0],
        "hourly_cloud": [40, 55, 70, 80, 75, 60],
        "hourly_wind_dir": [180, 200, 240, 250],
        "hourly_rh": [70, 72, 78, 82, 80, 76],
        "hourly_temp": [34, 33, 32, 31, 30, 29],
        "hourly_prob": [20, 40, 70, 80, 60, 40, 20, 10, 10, 10],
        "precip_today_mm": 8,
        "precip_3d_mm": 20,
        "precip_z": 0.4,
        "daily_times": ["2026-08-18"],
        "temp_max": [34],
        "rh_now": 72,
        "coast_km": 2,
    }
    loc = _loc()
    pack = build(f, loc, hy={"memory": 0.6, "limb": "wetting", "flip": "runoff"})
    hours = [h["mm"] for h in pack["hours"]]
    locked = [h["mm"] for h in pack["locked"]["hours"]]
    assert hours == locked
    sat = pack.get("sat") or {}
    assert sat.get("engine") == "sat_kalman"
    assert sat.get("rewrites_locked") is False
    assert sat.get("source_kind") == "model-analysis"
    assert sat.get("locked_mm_ref") == hours
    # Re-pack must not change the locked list sitting on the nowcast.
    blob = sk.pack(
        loc,
        sat_obs.from_open_meteo_hours(f["hourly_times"], f["hourly_precip"], now_iso="2026-08-18T12:05:00")["knots"],
        source="om-analysis",
        source_kind="model-analysis",
        stride_s=1,
    )
    assert [h["mm"] for h in pack["hours"]] == hours
    assert blob["source_kind"] == "model-analysis"
    assert "Open-Meteo" in blob["note"]
    assert "not INSAT" in blob["note"] or "not INSAT/IMERG" in blob["note"]


def test_history_causal_and_offset_identity():
    knots = _knots([0.5, 4.0, 4.0, 1.0])
    hist = sk.replay_history(knots, stride_s=300)
    scenes = hist["scenes"]
    assert len(scenes) == 4
    for sc in scenes:
        assert abs(sc["y"] - (sc["obs"] - sc["pred"])) < 1e-6
    # Arrival prediction at the 4 mm/h scene must not already be 4.
    assert scenes[1]["pred"] < 3.0
    assert scenes[1]["obs"] == 4.0
    # Later scene around 4 should be closer than the first jump.
    assert abs(scenes[2]["y"]) < abs(scenes[1]["y"])
    # Predicted path exists between first and second scene.
    preds = [p for p in hist["series"] if p.get("pred") is not None]
    assert len(preds) > 4
    # No future leak: a mid-gap pred before the 4 mm/h knot stays below that obs.
    first_t = knots[0]["t"][:16]
    mid = [p for p in hist["series"] if p.get("pred") is not None and first_t < p["t"][:16] < knots[1]["t"][:16]]
    assert mid
    assert all(p["pred"] < 3.5 for p in mid)


def test_history_curves_with_physical_drivers():
    from app.science.sat_phys import drivers_from_features

    t0 = datetime(2026, 8, 18, 10, 0, tzinfo=IST)
    times = [(t0 + timedelta(hours=i)).isoformat(timespec="seconds") for i in range(4)]
    f = {
        "hourly_times": times,
        "hourly_precip": [0.4, 2.2, 2.0, 0.6],
        "hourly_cloud": [55, 80, 85, 60],
        "hourly_rh": [78, 88, 90, 80],
        "hourly_cape": [400, 1400, 1100, 300],
        "hourly_weather_code": [61, 95, 80, 61],
        "hourly_temp": [33, 32, 31, 30],
        "hourly_dew": [26, 27, 27, 25],
        "coast_km": 3,
    }
    drv = drivers_from_features(
        f,
        _loc(),
        {
            "regime": {"name": "cell"},
            "kal": {"level": "watch"},
            "stream": {"eta_h": 0.35},
            "advection": {"upstream_mm": 1.8, "speed_kmh": 16},
        },
    )
    hist = sk.replay_history(_knots([0.4, 2.2, 2.0, 0.6], t0), stride_s=60, drivers=drv)
    hour = [p for p in hist["series"] if p.get("pred") is not None and "T11:" in p["t"]]
    vals = [p["pred"] for p in hour]
    assert vals
    assert max(vals) - min(vals) > 0.2


def test_pack_includes_history(tmp_path, monkeypatch):
    monkeypatch.setattr(sk, "STATE_PATH", tmp_path / "k.json")
    loc = _loc()
    blob = sk.pack(
        loc,
        _knots([1.0, 2.0, 0.5]),
        source="om-analysis",
        source_kind="model-analysis",
        stride_s=60,
        reset=True,
    )
    hist = blob.get("history") or {}
    assert hist.get("scenes")
    assert hist.get("series")
    assert hist["scenes"][0]["obs"] == 1.0


def test_pack_formula_matches_predict(tmp_path, monkeypatch):
    monkeypatch.setattr(sk, "STATE_PATH", tmp_path / "k.json")
    loc = _loc()
    knots = _knots([1.5, 2.0])
    blob = sk.pack(
        loc,
        knots,
        source="om-analysis",
        source_kind="model-analysis",
        stride_s=1,
        now=datetime(2026, 8, 18, 10, 30, tzinfo=IST),
        reset=True,
    )
    form = blob["formula"]
    assert form["kind"] == "decay_bias_v1"
    assert form["eps"] == sk.EPS
    st = {"x": form["x"]}
    assert abs(sk.predict_rate(st, 0.0) - sk.rate_from_x(form["x"])) < 1e-6
    assert blob["stride_s"] == 1
    assert blob["pred_series"]
    assert blob["n_updates"] == 2

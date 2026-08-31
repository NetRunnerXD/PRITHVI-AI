from app.ml.vera.extremes import run as extremes_run
from app.ml.vera.gate import run as gate_run
from app.ml.vera.hourly import build
from app.ml.vera.verify import LOG, ingest_forecast, run as verify_run, walk_forward_cv


def test_leads_and_intra_and_bulletin():
    from app.ml.vera.disagreement import run as disag_run
    from app.ml.vera.intra_hour import _hour_minutes, run as intra_run
    from app.ml.vera.leads import run as leads_run
    from app.ml.vera.pipeline import build_vera
    from app.schemas.location import Location

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
    times = [f"2026-08-30T{h:02d}:00+05:30" for h in range(24)] + [f"2026-08-31T{h:02d}:00+05:30" for h in range(24)]
    f = {
        "precip_days": [12.0, 4.0, 1.0, 0.0, 2.0, 3.0, 1.0, 0.5, 0.2, 0.1],
        "temp_max": [33, 34, 32, 31, 30, 29, 28, 27, 26, 25],
        "temp_min": [25, 25, 24, 24, 23, 23, 22, 22, 21, 21],
        "wind_max": [20, 22, 18, 16, 14, 12, 10, 10, 9, 8],
        "hourly_precip": [0.5] * 48,
        "hourly_temp": [30] * 48,
        "hourly_wind": [12] * 48,
        "hourly_times": times,
        "members": {
            "ifs025": {"precip_days": [20.0, 5.0], "temp_max": [34], "wind_max": [22], "hourly_precip": [0.6] * 48},
            "gfs": {"precip_days": [4.0, 3.0], "temp_max": [32], "wind_max": [18], "hourly_precip": [0.2] * 48},
        },
    }
    leads = leads_run(f, f["members"], {"ifs025": 0.6, "gfs": 0.4})
    assert [r["lead_h"] for r in leads] == [24, 72, 120, 240]
    assert leads[0]["rain"]["q50"] is not None
    mins = _hour_minutes(10.0, 30, 31, 10, 12, 70, times[0], stride_min=5)
    assert abs(sum(m["rain_mm"] for m in mins) - 10.0) < 1e-6
    from datetime import date as date_cls

    intra = intra_run(f, blend_hourly=[0.4] * 48, today=date_cls(2026, 8, 30))
    assert intra["days"]
    assert intra["days"][0]["label"] == "Today"
    assert intra["days"][0].get("minutes_today")
    d = disag_run(f["members"], {"q50": 40, "extremes": {"p_ge_64_5": 0.4}}, leads)
    assert d["rain"] > 0
    pack = build_vera(f, loc, {"ok": True, "insat": {"ok": True, "url": "https://example/ir.jpg"}}, f["members"])
    assert pack["bulletin"]
    assert pack["leads"]
    assert pack["intra_hour"]["days"]
    assert pack["replay"]["cases"]
    assert pack["gate"]["explain"]
    hour = {r["lead_h"]: r for r in pack["hourly"]}
    ext_h = {r["h"]: r for r in (pack.get("extremes") or {}).get("compare", {}).get("hourly") or []}
    if 0 in hour and 0 in ext_h:
        assert ext_h[0]["blend_mm"] == hour[0]["moe"]
        assert ext_h[0]["website_mm"] == hour[0]["om"]
        assert ext_h[0]["ensemble_mm"] == hour[0]["ensemble"]


def test_hourly_48():
    f = {"hourly_precip": [0.1] * 48, "hourly_times": [f"2026-08-30T{h:02d}:00" for h in range(24)] + [f"2026-08-31T{h:02d}:00" for h in range(24)]}
    members = {"ifs025": {"hourly_precip": [0.2] * 48}, "gfs": {"hourly_precip": [0.0] * 48}}
    rows = build(f, members, {"ifs025": 0.6, "gfs": 0.4}, [0.12] * 48, "22.1,88.1")
    assert [r["lead_h"] for r in rows] == list(range(0, 48))
    assert rows[0]["members"]["ifs025"] == 0.2
    assert rows[0]["moe"] == 0.12  # 0.6*0.2 + 0.4*0.0


def test_hourly_includes_past_12_with_negative_leads():
    times = [f"2026-08-30T{h:02d}:00+05:30" for h in range(24)] + [f"2026-08-31T{h:02d}:00+05:30" for h in range(24)]
    precip = [float(i) for i in range(48)]
    f = {"hourly_precip": precip, "hourly_times": times, "hourly_now_i": 12}
    members = {"ifs025": {"hourly_precip": precip}, "gfs": {"hourly_precip": precip}}
    rows = build(f, members, {"ifs025": 0.5, "gfs": 0.5}, precip, "22.1,88.1")
    leads = [r["lead_h"] for r in rows]
    assert leads[0] == -12
    assert 0 in leads
    assert leads[-1] == 35
    assert rows[0]["om"] == 0.0
    now_row = next(r for r in rows if r["lead_h"] == 0)
    assert now_row["om"] == 12.0


def test_verify_and_cv(tmp_path, monkeypatch):
    monkeypatch.setattr("app.ml.vera.verify.LOG", tmp_path / "log.jsonl")
    rows = []
    for i in range(36):
        rows.append(
            {
                "t": f"2026-08-29T{i%24:02d}:00",
                "pin": "p",
                "ensemble": 1.0 + i * 0.01,
                "om": 1.1,
                "members": {"ifs025": 0.8, "gfs": 1.2},
                "obs": 1.05,
                "obs_source": "open-meteo-analysis",
            }
        )
    ingest_forecast(rows)
    pack = verify_run("p", rows[:2], {"hourly_times": [], "hourly_precip": []})
    assert pack["scores"]["ensemble"]["n"] >= 1
    assert pack["scores"]["ensemble"]["mae"] is not None
    cv = walk_forward_cv("p", fold_h=12)
    assert cv["folds"] >= 1
    assert pack["scores"]["skill_vs_om"] is None
    assert pack["independent_obs"] is False


def test_skill_omitted_when_obs_is_om(tmp_path, monkeypatch):
    from app.ml.vera import verify as v

    monkeypatch.setattr(v, "LOG", tmp_path / "log.jsonl")
    rows = [
        {"t": "2026-08-29T00:00", "lead_h": 1, "pin": "p", "ensemble": 1.0, "om": 1.1, "members": {}, "obs": 1.1, "obs_source": "open-meteo-analysis"}
    ]
    v.ingest_forecast(rows)
    sc = v.scores("p")
    assert sc["skill_vs_om"] is None
    assert sc["independent_obs"] is False


def test_leads_do_not_clobber(tmp_path, monkeypatch):
    from app.ml.vera import verify as v

    monkeypatch.setattr(v, "LOG", tmp_path / "log.jsonl")
    v.ingest_forecast(
        [
            {"t": "2026-08-29T03:00", "lead_h": 1, "pin": "p", "ensemble": 0.2, "om": 0.1, "members": {}},
            {"t": "2026-08-29T03:00", "lead_h": 24, "pin": "p", "ensemble": 0.9, "om": 0.1, "members": {}},
        ]
    )
    loaded = v._load()
    assert len(loaded) == 2


def test_independent_imerg_obs(tmp_path, monkeypatch):
    from app.ml.vera import verify as v

    monkeypatch.setattr(v, "LOG", tmp_path / "log.jsonl")
    rows = [
        {
            "t": f"2026-08-28T{h:02d}:00",
            "lead_h": h,
            "pin": "p",
            "ensemble": 0.4,
            "moe": 0.3,
            "om": 0.2,
            "members": {"gfs": 0.2},
        }
        for h in range(6)
    ]
    pack = v.run(
        "p",
        rows,
        {"hourly_times": [f"2026-08-28T{h:02d}:00" for h in range(6)], "imerg_hourly": [0.35] * 6},
    )
    assert pack["independent_obs"] is True
    assert pack["n_verified"] >= 1
    assert pack["scores"]["skill_vs_om"] is not None
    assert pack["agreement"]["ensemble"]["n"] >= 1
    assert pack["hourly_history"]


def test_extremes_heat_wind_rain():
    f = {
        "temp_max": [41.0, 42.0, 39.0],
        "hourly_temp": [38] * 48,
        "hourly_wind": [20] * 10 + [65] * 2 + [15] * 36,
        "hourly_precip": [3.0] * 24,
        "precip_days": [80.0],
        "clim_tmax_c": 35.0,
    }
    members = {"ifs025": {"precip_days": [80.0], "temp_max": [41, 42]}}
    pack = extremes_run(f, members, {"ifs025": 1.0}, {"extremes": {"p_ge_64_5": 0.5, "p_ge_115_6": 0.1}})
    assert pack["heat_wave"]["consecutive"] >= 2
    assert pack["high_wind"]["peak_kmh"] >= 60
    assert pack["heavy_rain"]["p"] >= 0.4
    assert pack["heat_wave"]["level"] in {"No alert", "Possible", "Warning"}
    assert pack["compare"]["hourly"]


def test_gate_reasons():
    g = gate_run(
        ["ifs025", "gfs"],
        {"ifs025": {"precip_days": [10]}, "gfs": {"precip_days": [8]}},
        {"ok": True, "derived": {"convective_initiation": True, "cold_cloud_frac": 0.1}, "embedding": [0] * 8},
        {"top": "active_monsoon", "soft_assignment": [1, 0]},
        {"embedding": [0] * 8},
        {},
        lead_hours=3,
    )
    assert "ifs025" in g["reasons"]
    assert "physics weather model" in g["reasons"]["ifs025"].lower() or "Physics" in g["reasons"]["ifs025"]
    assert g["confidence"]["ifs025"] >= 28
    assert abs(sum(g["weights"].values()) - 1) < 0.01

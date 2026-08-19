from types import SimpleNamespace

from app.providers.weatherbit_lightning import parse_payload
from app.science.convective import build
from app.science.sat_cv import forecast_track, ir_rain_mmh, pin_eta_min, segment, track


def _grid_cell(tb_core: float = 210.0, tb_out: float = 260.0, n: int = 24) -> list[list[float]]:
    g = [[tb_out] * n for _ in range(n)]
    for y in range(9, 15):
        for x in range(9, 15):
            g[y][x] = tb_core
    g[12][12] = tb_core - 12
    return g


def test_ir_rain_colder_is_heavier():
    assert ir_rain_mmh(270) == 0
    assert ir_rain_mmh(210) > ir_rain_mmh(240)


def test_segment_finds_deep_cell():
    cells = segment(_grid_cell(), lat0=22.07, lon0=88.07, half_deg=1.1)
    assert cells
    assert cells[0]["min_tb_k"] < 221
    assert cells[0]["ot"] is True
    assert cells[0]["rain_ir_mm_h"] > 0


def test_track_motion_and_collapse():
    a = segment(_grid_cell(210), lat0=22.07, lon0=88.07)
    b = segment(_grid_cell(225), lat0=22.10, lon0=88.12)
    out = track(a, b, 10.0)
    assert out
    assert out[0]["trend"] in {"collapsing", "steady", "growing"}
    assert "u_kmh" in out[0]


def test_eta_and_forecast():
    cell = {"lat": 22.07, "lon": 88.07, "u_kmh": 40.0, "v_kmh": 0.0, "area_km2": 400, "rain_ir_mm_h": 12.0, "trend": "growing"}
    eta = pin_eta_min(cell, 22.07, 88.40)
    assert eta is None or eta >= 0
    fut = forecast_track(cell)
    assert [r["lead_min"] for r in fut] == [15, 30, 60]


def test_weatherbit_parse():
    raw = {
        "data": [
            {"lat": 22.1, "lon": 88.1, "distance": 12.4, "timestamp_utc": "2026-08-19T08:00:00"},
            {"lat": 22.4, "lon": 88.5, "distance": 55.0, "timestamp_utc": "2026-08-19T08:01:00"},
        ]
    }
    out = parse_payload(raw, 22.07, 88.07)
    assert out["ok"] is True
    assert out["n"] == 2
    assert out["nearest_km"] == 12.4


def test_cloudburst_and_downburst_from_live_cell():
    cells = segment(_grid_cell(208), lat0=22.07, lon0=88.07)
    cells = track([], cells, 10)
    if cells:
        cells[0]["trend"] = "growing"
        cells[0]["speed_kmh"] = 8
    loc = SimpleNamespace(lat=22.07, lon=88.07, state="West Bengal", district="Purba Medinipur", place_name="Haldia")
    live = {
        "as_of": "2026-08-19T08:00:00+00:00",
        "insat": {"ok": True, "tb_k": 208.0, "source": "imd-insat-ir1"},
        "imerg": {"ok": True, "mm_h": 18.0},
        "lightning": {
            "ok": True,
            "source": "weatherbit-lightning",
            "strokes": [{"lat": 22.08, "lon": 88.08, "distance_km": 6.0}],
            "nearest_km": 6.0,
        },
        "cells": cells,
    }
    f = {"hourly_cape": [1800], "hourly_gust": [58], "hourly_wind": [22], "hourly_precip": [5]}
    pack = build(f, loc, live=live, phys={"kind": "hugli", "pond_scale": 1.0})
    assert pack["lightning"]["detected"] is True
    assert pack["lightning"]["level"] in {"watch", "alert"}
    assert pack["cloudburst"]["score_pct"] >= 45
    assert pack["cloudburst"]["rain_sat_mm_h"] > 0


def test_downburst_on_collapse():
    loc = SimpleNamespace(lat=26.91, lon=75.79, state="Rajasthan", district="Jaipur", place_name="Jaipur")
    cell = {
        "id": "c0",
        "lat": 26.91,
        "lon": 75.79,
        "min_tb_k": 230,
        "area_km2": 200,
        "ot": False,
        "rain_ir_mm_h": 6,
        "trend": "collapsing",
        "d_tb_k": 4.0,
        "u_kmh": 5,
        "v_kmh": 0,
        "speed_kmh": 5,
    }
    f = {"hourly_cape": [1400], "hourly_gust": [62], "hourly_wind": [28], "hourly_precip": [3]}
    pack = build(f, loc, live={"cells": [cell], "lightning": {"ok": True, "strokes": [], "nearest_km": None}}, phys={"kind": "plateau"})
    assert pack["downburst"]["score_pct"] >= 45


def test_locked_hours_untouched_by_convective(monkeypatch):
    from datetime import datetime
    from app.science import nowcast as nc
    from app.science.nowcast import IST, build as nc_build

    monkeypatch.setattr(nc, "_now", lambda: datetime(2026, 8, 18, 12, 5, tzinfo=IST))
    f = {
        "hourly_times": [f"2026-08-18T{h:02d}:00" for h in range(10, 16)],
        "hourly_precip": [0.2, 1.0, 2.0, 1.0, 0.4, 0.1],
        "hourly_cape": [400],
        "hourly_gust": [20],
        "hourly_wind": [12],
        "daily_times": ["2026-08-18"],
        "precip_z": 0.0,
        "precip_3d_mm": 4,
    }
    loc = SimpleNamespace(lat=22.07, lon=88.07, district="Purba Medinipur", place_name="Haldia", place_kind="city", state="West Bengal")
    pack = nc_build(f, loc, hy={"memory": 0.4, "limb": "drying"}, live_sat={"ok": False, "cells": []})
    hours = pack["hours"]
    assert all("mm" in h for h in hours)
    assert pack["locked"]["hours"][0]["mm"] == hours[0]["mm"]
    assert "convective" in pack

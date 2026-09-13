from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from app.science.env_hazards import (
    compound_uv_heat,
    fog_nowcast,
    heatwave_nowcast,
    uv_nowcast,
)
from app.science.sat_cv import ir_rain_mmh, track
from app.science.thunder_predict import agreement_gate
from app.science.cv_nowcast import lightning_prob, schultz_jump
from app.services.snapshot import _warnings


IST = timezone(timedelta(hours=5, minutes=30))


def _loc(**kw):
    return SimpleNamespace(
        district=kw.get("district", "New Delhi"),
        state=kw.get("state", "Delhi"),
        lat=kw.get("lat", 28.61),
        lon=kw.get("lon", 77.21),
        place_name=kw.get("place", "Delhi"),
        id="pin",
        label="Delhi",
    )


def test_fog_dense_window_from_vis_series():
    now = datetime(2026, 1, 12, 3, 0, tzinfo=IST)
    times = [(now + timedelta(hours=i)).strftime("%Y-%m-%dT%H:00") for i in range(8)]
    f = {
        "hourly_times": times,
        "hourly_now_i": 0,
        "hourly_vis": [120, 80, 150, 400, 900, 2000, 4000, 5000],
        "hourly_rh": [96] * 8,
        "hourly_dew": [8] * 8,
        "hourly_temp": [9] * 8,
        "hourly_wind": [4] * 8,
        "hourly_weather_code": [45, 45, 45, 3, 3, 1, 1, 1],
        "hourly_is_day": [0, 0, 0, 0, 1, 1, 1, 1],
        "state": "Delhi",
    }
    fog = fog_nowcast(f, loc=_loc(), now=now)
    assert fog["alert"] is True
    assert fog["grade"] in {"dense", "very_dense"}
    assert fog["window_start"]
    assert fog["window_end"]
    assert fog["p_fog"] >= 0.55


def test_heatwave_plains_needs_two_days():
    loc = _loc(district="Jaipur", state="Rajasthan", lat=26.9, lon=75.8)
    f = {
        "temp_max": [42.0, 41.5, 38.0],
        "temp_min": [28, 27, 26],
        "clim_tmax_c": 36.0,
        "daily_times": ["2026-05-20", "2026-05-21", "2026-05-22"],
        "hourly_temp": [34] * 24,
        "hourly_rh": [30] * 24,
        "hourly_now_i": 0,
        "lat": 26.9,
        "lon": 75.8,
    }
    hw = heatwave_nowcast(f, loc=loc, now=datetime(2026, 5, 20, 8, tzinfo=IST))
    assert hw["imd_qualifies"] is True
    assert hw["zone"] == "plains"
    assert hw["threshold_c"] == 40.0
    assert hw["alert"] is True
    assert hw["window_start"]
    assert hw["window_end"]


def test_heatwave_hills_threshold_30():
    loc = _loc(district="Darjeeling", state="West Bengal", lat=27.04, lon=88.26)
    f = {
        "temp_max": [32.0, 31.5],
        "clim_tmax_c": 26.0,
        "daily_times": ["2026-05-20", "2026-05-21"],
        "hourly_temp": [22] * 12,
        "hourly_rh": [40] * 12,
        "lat": 27.04,
        "lon": 88.26,
    }
    hw = heatwave_nowcast(f, loc=loc, now=datetime(2026, 5, 20, 8, tzinfo=IST))
    assert hw["zone"] == "hills"
    assert hw["threshold_c"] == 30.0
    assert hw["imd_qualifies"] is True


def test_uv_very_high_window():
    now = datetime(2026, 5, 20, 8, tzinfo=IST)
    times = [(now + timedelta(hours=i)).strftime("%Y-%m-%dT%H:00") for i in range(10)]
    f = {
        "hourly_uv": [1, 3, 6, 9, 11, 10, 7, 4, 2, 1],
        "hourly_aqi_times": times,
        "hourly_aqi_now_i": 0,
        "uv_index_max": 11,
    }
    uv = uv_nowcast(f, now=now)
    assert uv["alert"] is True
    assert uv["who_category"] in {"very_high", "extreme"}
    assert uv["window_start"]
    assert uv["window_end"]


def test_compound_uv_heat():
    heat = {"humid_heat": True, "imd_qualifies": False, "wbgt_peak_c": 30.0, "window_start": "a", "window_end": "b"}
    uv = {"alert": True, "uv_peak": 9.0, "window_start": "a", "window_end": "b"}
    c = compound_uv_heat(heat, uv)
    assert c and c["alert"] is True


def test_he_lite_zero_on_warm_anvil():
    assert ir_rain_mmh(270) == 0
    assert ir_rain_mmh(210) > ir_rain_mmh(240)
    assert ir_rain_mmh(210, surround_tb=212) == 0
    assert ir_rain_mmh(210, surround_tb=240, ot=True) > 0


def test_overlap_track_keeps_id():
    a = [{"id": "c0", "lat": 22.5, "lon": 88.3, "min_tb_k": 210, "area_km2": 80, "pix": [10, 11, 12, 13]}]
    b = [{"id": "c9", "lat": 22.51, "lon": 88.31, "min_tb_k": 208, "area_km2": 90, "pix": [11, 12, 13, 14]}]
    out = track(a, b, 15.0)
    assert out[0]["id"] == "c0"
    assert out[0]["age_min"] >= 15
    assert out[0]["overlap"] and out[0]["overlap"] >= 0.15


def test_schultz_needs_flash_rate_not_ot_pixels():
    quiet = schultz_jump([], 100)
    assert quiet["jump"] is False
    bursts = [{"past_mins": m} for m in (1, 1.5, 2, 2.2, 3, 12, 16, 18)]
    jumped = schultz_jump(bursts, 80)
    assert jumped["n"] >= 4
    assert "fr_per_min" in jumped


def test_agreement_gate_blocks_ir_only():
    g = agreement_gate(p_lightning=0.4, ot=True, cape=200, weather_code=3, n_strokes=0)
    assert g["ok"] is False
    assert g["status"] == "unverified"
    ok = agreement_gate(p_lightning=0.4, ot=True, cape=1200, weather_code=95, n_strokes=0)
    assert ok["ok"] is True
    live = agreement_gate(p_lightning=0.1, ot=False, n_strokes=2)
    assert live["ok"] is True


def test_ot_heuristic_still_high_prob():
    cell = {"min_tb_k": 208, "ot": True, "rain_ir_mm_h": 22, "speed_kmh": 8, "trend": "growing"}
    cool = {"d_tb": 2.0, "jump": 3}
    assert lightning_prob(cell, cool, 8) > 0.45


def test_fog_uv_heat_enter_alerts():
    from app.schemas.location import Location

    loc = Location(
        id="in_dl",
        label="New Delhi, Delhi",
        state="Delhi",
        district="New Delhi",
        lat=28.61,
        lon=77.21,
    )
    now = datetime(2026, 1, 12, 3, 0, tzinfo=IST)
    times = [(now + timedelta(hours=i)).strftime("%Y-%m-%dT%H:00") for i in range(6)]
    f = {
        "hourly_times": times,
        "hourly_now_i": 0,
        "hourly_vis": [80, 90, 120, 400, 2000, 4000],
        "hourly_rh": [95] * 6,
        "hourly_dew": [7] * 6,
        "hourly_temp": [8] * 6,
        "hourly_wind": [3] * 6,
        "hourly_weather_code": [45, 45, 3, 1, 1, 1],
        "hourly_is_day": [0, 0, 0, 1, 1, 1],
        "hourly_uv": [1, 2, 8, 10, 9, 4],
        "hourly_aqi_times": times,
        "hourly_aqi_now_i": 0,
        "temp_max": [42, 41],
        "clim_tmax_c": 36,
        "daily_times": ["2026-05-20", "2026-05-21"],
        "hourly_temp": [34] * 6,
        "weather_code": 1,
    }
    out = _warnings(loc, [], 10, f, [], [], None)
    kinds = {w.kind for w in out}
    assert "fog" in kinds
    fog = next(w for w in out if w.kind == "fog")
    assert fog.window_start
    assert fog.window_end

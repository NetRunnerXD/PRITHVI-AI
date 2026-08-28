from datetime import datetime

from app.science.live import gap_series, hugli_station, playhead, tide_height_m
from app.science.nowcast import IST, build
from types import SimpleNamespace


def test_gap_integrates_to_locked_hours():
    hours = [
        {"t": "2026-08-18T13:00:00", "mm": 2.0, "lead_h": 1, "engine": "nowcast", "p_wet": 0.6},
        {"t": "2026-08-18T14:00:00", "mm": 1.0, "lead_h": 2, "engine": "nowcast", "p_wet": 0.4},
    ]
    gap = gap_series(hours, dt_s=60)
    assert gap["series"]
    assert abs(gap["checksum_mm"] - 3.0) < 0.05
    first = [p for p in gap["series"] if p["lead_h"] == 1]
    assert abs(sum(p["mm"] for p in first) - 2.0) < 0.05


def test_haldia_tide_station():
    assert hugli_station(22.0667, 88.0698, "Haldia") == "Haldia"
    h = tide_height_m(datetime(2026, 8, 18, 14, 0, tzinfo=IST), "Haldia")
    assert 0.5 < h["tide_m"] < 6.0
    assert "gauge" in h["note"].lower() or "not a" in h["note"].lower()


def test_playhead_does_not_invent_hour_total():
    hours = [{"t": "2026-08-18T13:00:00", "mm": 1.2, "lead_h": 1, "engine": "nowcast", "p_wet": 0.5}]
    pack = {
        "hours": hours,
        "gap": gap_series(hours),
        "clock": {"t_start": "2026-08-18T13:20:00"},
        "ponding": {"factor": 0.3},
        "pump": {"action": "hold"},
        "access": {"enterable": False},
        "place": {"name": "Haldia", "lat": 22.07, "lon": 88.07},
    }
    ph = playhead(pack, now=datetime(2026, 8, 18, 13, 10, tzinfo=IST))
    assert ph["pump"] == "hold"
    assert ph["enterable"] is False
    assert ph["seconds_to_onset"] == 600
    assert "1 Hz" in ph["note"] or "cursor" in ph["note"]


def test_build_attaches_gap(monkeypatch):
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
    loc = SimpleNamespace(district="Purba Medinipur", lat=22.07, lon=88.07, place_kind="city", place_name="Haldia")
    pack = build(f, loc, hy={"memory": 0.6, "limb": "wetting", "flip": "runoff"})
    assert pack.get("gap", {}).get("series")
    assert abs(pack["gap"]["checksum_mm"] - pack["gap"]["locked_mm"]) < 0.05
    assert pack.get("playhead", {}).get("tide_station") == "Haldia"
    sat = pack.get("sat") or {}
    assert sat.get("engine") == "sat_kalman"
    assert sat.get("rewrites_locked") is False
    assert sat.get("source_kind") in {"model-analysis", "satellite-qpe"}

"""Predicted tab: dual 7-day series is built from the pin's Open-Meteo row, not another HQ."""

from app.ml.outlook import build_hourly_7d, build_outlook
from .isolation import loc


def test_outlook_days_stay_numeric_for_the_pin():
    home = loc("Howrah")
    f = {
        "precip_days": [4.2, 1.0, 0.0],
        "precip_prob": [70, 40, 20],
        "temp_max": [32.1, 31.0, 30.5],
        "temp_min": [25.0, 24.5, 24.0],
        "et0_days": [3.0, 3.1, 3.2],
        "daily_times": ["2026-08-19", "2026-08-20", "2026-08-21"],
        "soil_m3m3": 0.3,
    }
    out = build_outlook(f)
    days = out.get("days") or []
    assert days
    assert days[0]["precip_mm"] == 4.2
    assert days[0]["temp_max_c"] == 32.1
    assert "Chhattisgarh" not in str(out)
    assert home.state == "West Bengal"


def test_vera_pack_on_models_tab():
    from app.ml.vera import build_vera

    home = loc("Howrah")
    pack = build_vera(
        {
            "precip_days": [4.2],
            "precip_3d_mm": 4.2,
            "clim_daily_mm": 6.0,
            "members": {"best_match": {"precip_days": [4.2]}},
            "daily_times": ["2026-08-19"],
        },
        home,
        {"ok": True, "insat": {"url": "https://mausam.imd.gov.in/Satellite/3Dasiasec_ir1.jpg"}},
        {"best_match": {"precip_days": [4.2]}},
    )
    assert pack["cv"]["frames"] is not None or pack["cv"]["insat_url"]
    assert "Chhattisgarh" not in str(pack)
    assert pack["graph"]["nodes"][0]["id"] == "data"
    assert pack["cv"]["map"]["asia"]["west"] == 40.0
    assert pack["cv"]["map"]["asia"]["east"] == 110.0
    assert pack["cv"]["map"]["asia"]["south"] == -10.0
    assert pack["cv"]["map"]["asia"]["url"] == "/api/sat/imd-asia"
    assert pack["cv"]["map"]["imerg_layer"] == "IMERG_Precipitation_Rate"
    assert pack["fusion"]["method"] == "EQMN"
    assert pack["parameters"]["n_total"] == 12


def test_contradiction_different_rain_does_not_copy():
    wet = build_outlook(
        {
            "precip_days": [40.0],
            "precip_prob": [90],
            "temp_max": [29.0],
            "temp_min": [24.0],
            "et0_days": [2.0],
            "daily_times": ["2026-08-19"],
            "soil_m3m3": 0.4,
        }
    )
    dry = build_outlook(
        {
            "precip_days": [0.0],
            "precip_prob": [10],
            "temp_max": [36.0],
            "temp_min": [26.0],
            "et0_days": [5.0],
            "daily_times": ["2026-08-19"],
            "soil_m3m3": 0.2,
        }
    )
    assert wet["days"][0]["precip_mm"] != dry["days"][0]["precip_mm"]


def test_hourly_7d_groups_by_date(monkeypatch):
    monkeypatch.setattr("app.ml.features._today_ist", lambda: "2026-08-30")
    times = []
    precip = []
    for d in range(30, 37):
        day = f"2026-08-{d:02d}" if d <= 31 else f"2026-09-{d - 31:02d}"
        for h in range(24):
            times.append(f"{day}T{h:02d}:00")
            precip.append(float(h % 5))
    out = build_hourly_7d(
        {
            "hourly_times": times,
            "hourly_precip": precip,
            "hourly_temp": [28.0] * len(times),
            "hourly_wind": [12.0] * len(times),
            "hourly_prob": [40] * len(times),
        }
    )
    dates = {row["date"] for row in out}
    assert "2026-08-30" in dates
    assert len(out) == 7 * 24
    day0 = [r for r in out if r["date"] == "2026-08-30"]
    assert len(day0) == 24
    assert day0[3]["hour"].startswith("03")
    assert day0[3]["precip_mm"] == 3.0


def test_hourly_7d_skips_yesterday(monkeypatch):
    monkeypatch.setattr("app.ml.features._today_ist", lambda: "2026-08-30")
    out = build_hourly_7d(
        {
            "hourly_times": ["2026-08-29T23:00", "2026-08-30T00:00", "2026-09-10T00:00"],
            "hourly_precip": [9.0, 1.0, 8.0],
            "hourly_temp": [20.0, 21.0, 22.0],
        }
    )
    assert [r["date"] for r in out] == ["2026-08-30"]
    assert out[0]["precip_mm"] == 1.0

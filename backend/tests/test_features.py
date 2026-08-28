from app.ml.features import extract, hourly_now_index, past_window, _hourly


def test_extract_3day_and_trend():
    om = {
        "current": {
            "temperature_2m": 28.0,
            "relative_humidity_2m": 80,
            "precipitation": 1.2,
            "weather_code": 61,
            "wind_speed_10m": 10,
            "wind_direction_10m": 210,
            "cloud_cover": 70,
            "is_day": 1,
            "visibility": 8000,
        },
        "hourly": {
            "time": [f"t{i}" for i in range(5)],
            "precipitation": [1, 0, 2, 0, 0],
            "temperature_2m": [27, 28, 29, 28, 27],
            "soil_moisture_0_to_7cm": [0.3, 0.31, 0.32, 0.31, 0.3],
            "relative_humidity_2m": [80, 81, 82, 80, 79],
            "wind_speed_10m": [8, 9, 10, 9, 8],
            "wind_direction_10m": [200, 210, 220, 200, 190],
        },
        "daily": {
            "time": ["d1", "d2", "d3"],
            "precipitation_sum": [10, 5, 2],
            "precipitation_probability_max": [80, 50, 20],
            "temperature_2m_max": [31, 32, 30],
            "temperature_2m_min": [24, 25, 24],
            "et0_fao_evapotranspiration": [3, 3.5, 4],
        },
    }
    flood = {"daily": {"river_discharge": [10, 14], "river_discharge_mean": [9, 10]}}
    marine = {"current": {"wave_height": 1.4, "wave_direction": 140, "wave_period": 6}, "hourly": {"wave_height": [1.2, 1.4]}}
    f = extract(om, flood, [4, 5, 6, 5, 4], marine=marine)
    assert f["precip_3d_mm"] == 17
    assert f["precip_today_mm"] == 10
    assert f["discharge_trend"] == "rising"
    assert len(f["hourly_temp"]) == 5
    assert f["soil_m3m3"] == 0.3
    assert f["wind_dir_now"] == 210
    assert f["wave_height_m"] == 1.4
    assert f["marine_inland"] is False


def test_extract_skips_yesterday_when_past_days(monkeypatch):
    from app.ml import features as feat

    monkeypatch.setattr(feat, "_today_ist", lambda: "2026-08-18")
    om = {
        "current": {},
        "hourly": {},
        "daily": {
            "time": ["2026-08-17", "2026-08-18", "2026-08-19"],
            "precipitation_sum": [82.6, 5.6, 4.4],
            "precipitation_probability_max": [90, 70, 40],
            "temperature_2m_max": [30, 31, 32],
            "temperature_2m_min": [25, 26, 26],
            "et0_fao_evapotranspiration": [3, 3, 3],
        },
    }
    f = extract(om, {}, [])
    assert f["precip_today_mm"] == 5.6
    assert f["precip_yesterday_mm"] == 82.6
    assert f["daily_times"][0] == "2026-08-18"
    assert f["precip_3d_mm"] == 5.6 + 4.4


def test_hourly_keeps_none_slots_aligned():
    om = {
        "hourly": {
            "time": ["2026-08-18T00:00", "2026-08-18T01:00", "2026-08-18T02:00"],
            "cape": [None, 800, None],
            "precipitation": [0.2, None, 1.1],
        }
    }
    cape = _hourly(om, "cape")
    rain = _hourly(om, "precipitation")
    assert len(cape) == 3 and len(rain) == 3
    assert cape[0] == 0.0 and cape[1] == 800.0
    assert rain[1] == 0.0 and rain[2] == 1.1


def test_hourly_now_index_and_soil_not_yesterday(monkeypatch):
    from datetime import datetime, timezone, timedelta
    from app.ml import features as feat

    IST = timezone(timedelta(hours=5, minutes=30))
    monkeypatch.setattr(feat, "_today_ist", lambda: "2026-08-18")
    times = [f"2026-08-17T{h:02d}:00" for h in range(24)] + [f"2026-08-18T{h:02d}:00" for h in range(24)]
    assert hourly_now_index(times, datetime(2026, 8, 18, 16, 10, tzinfo=IST)) == 24 + 16
    om = {
        "current": {},
        "hourly": {
            "time": times,
            "soil_moisture_0_to_7cm": [0.11] * 24 + [0.33] * 24,
            "precipitation": [1.0] * 24 + [0.0] * 24,
        },
        "daily": {
            "time": ["2026-08-17", "2026-08-18"],
            "precipitation_sum": [80.0, 2.0],
            "precipitation_probability_max": [90, 20],
            "temperature_2m_max": [30, 31],
            "temperature_2m_min": [24, 25],
            "et0_fao_evapotranspiration": [3, 3],
        },
    }
    monkeypatch.setattr(feat, "hourly_now_index", lambda times, now=None: 24 + 16)
    f = extract(om, {}, [])
    assert f["soil_m3m3"] == 0.33
    assert f["precip_today_mm"] == 2.0
    recent = past_window(f["hourly_precip"], f["hourly_now_i"], 6)
    assert len(recent) <= 6
    assert all(x == 0.0 for x in recent)

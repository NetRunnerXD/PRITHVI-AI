from types import SimpleNamespace

from app.providers.firms import cluster, parse_csv
from app.science.landslide import nowcast
from app.services.snapshot import _warnings
from app.schemas.location import Location


def test_parse_csv_keeps_india_drops_foreign():
    text = (
        "latitude,longitude,frp,confidence,acq_date,acq_time\n"
        "22.5,88.3,12.0,h,2026-09-13,0630\n"
        "14.6,121.0,40.0,h,2026-09-13,0630\n"
    )
    rows = parse_csv(text)
    assert len(rows) == 1
    assert rows[0]["lat"] == 22.5
    assert rows[0]["source"] == "nasa-firms-viirs"
    assert rows[0]["occurred_ms"]
    assert rows[0]["t"]


def test_cluster_requires_mass_or_frp():
    from datetime import datetime, timezone

    t = datetime(2026, 9, 13, 6, 30, tzinfo=timezone.utc)
    pts = [
        {"lat": 22.50, "lon": 88.30, "frp": 2.0, "confidence": "n", "t_utc": t},
        {"lat": 22.51, "lon": 88.31, "frp": 3.0, "confidence": "n", "t_utc": t},
        {"lat": 26.9, "lon": 75.8, "frp": 1.0, "confidence": "l", "t_utc": t},
    ]
    out = cluster(pts)
    assert any(c["n"] >= 2 for c in out)
    assert all(c["kind"] == "fire" for c in out)


def test_landslide_orographic_heavy_rain_alerts():
    loc = SimpleNamespace(lat=27.04, lon=88.26, state="West Bengal", district="Darjeeling")
    quiet = nowcast({"precip_3d_mm": 8, "soil_m3m3": 0.22, "hourly_precip": [0], "hourly_now_i": 0}, loc=loc)
    wet = nowcast({"precip_3d_mm": 80, "soil_m3m3": 0.38, "hourly_precip": [10], "hourly_now_i": 0}, loc=loc)
    assert quiet["alert"] is False
    assert wet["alert"] is True
    assert wet["window_start"]
    assert wet["window_end"]
    assert wet["window_h"] == 12
    assert wet["phys"] == "orographic"
    mid = nowcast({"precip_3d_mm": 30, "soil_m3m3": 0.30, "hourly_precip": [5], "hourly_now_i": 0}, loc=loc)
    if mid["level"] == "watch":
        assert mid["window_h"] == 6
        assert mid["window_start"]


def test_landslide_and_fire_enter_alerts():
    loc = Location(
        id="in_wb_darj",
        label="Darjeeling, West Bengal",
        state="West Bengal",
        district="Darjeeling",
        lat=27.04,
        lon=88.26,
    )
    fires = [
        {
            "id": "firms-1",
            "lat": 27.05,
            "lon": 88.27,
            "n": 6,
            "frp_mw": 22.0,
            "place": "Darjeeling, West Bengal",
            "state": "West Bengal",
        }
    ]
    f = {
        "precip_3d_mm": 85,
        "soil_m3m3": 0.4,
        "hourly_precip": [12],
        "hourly_now_i": 0,
        "weather_code": 1,
        "hourly_vis": [8000],
        "hourly_rh": [70],
        "hourly_temp": [18],
        "hourly_dew": [14],
        "hourly_wind": [8],
        "hourly_weather_code": [3],
        "hourly_is_day": [1],
        "hourly_times": ["2026-09-13T12:00"],
    }
    out = _warnings(loc, [], 10, f, [], [], None, fires=fires)
    kinds = {w.kind for w in out}
    assert "fire" in kinds
    assert "landslide" in kinds
    fire = next(w for w in out if w.kind == "fire")
    assert fire.lat is not None

from datetime import datetime, timezone

from app.providers.gdacs import parse_events
from app.providers.open_meteo import _FC_CURRENT, _FC_DAILY, _FC_HOURLY, _merge_om
from app.science.astro import moon_illumination, moon_rise_set


def test_om_request_covers_quality_doc_weather():
    blob = ",".join([_FC_CURRENT, _FC_HOURLY, _FC_DAILY])
    for token in (
        "relative_humidity_2m",
        "dew_point_2m",
        "apparent_temperature",
        "precipitation_probability",
        "rain",
        "showers",
        "snowfall",
        "snow_depth",
        "weather_code",
        "pressure_msl",
        "surface_pressure",
        "cloud_cover_low",
        "visibility",
        "evapotranspiration",
        "et0_fao_evapotranspiration",
        "vapour_pressure_deficit",
        "wind_gusts_10m",
        "sunrise",
        "sunset",
        "daylight_duration",
        "sunshine_duration",
        "shortwave_radiation_sum",
        "uv_index_max",
    ):
        assert token in blob


def test_merge_om_keeps_core_and_adds_extra():
    a = {"hourly": {"temperature_2m": [1], "time": ["t"]}}
    b = {"hourly": {"soil_temperature_0cm": [18]}}
    m = _merge_om(a, b)
    assert m["hourly"]["temperature_2m"] == [1]
    assert m["hourly"]["soil_temperature_0cm"] == [18]


def test_gdacs_filters_india_box():
    rows = [
        {"eventtype": "FL", "latitude": 22.0, "longitude": 88.0, "name": "Hugli", "eventid": "1"},
        {"eventtype": "EQ", "latitude": 40.0, "longitude": 10.0, "name": "Italy", "eventid": "2"},
    ]
    out = parse_events(rows)
    assert len(out) == 1
    assert out[0]["source"] == "GDACS"
    assert out[0]["event_type"] == "FL"


def test_moon_phase_is_bounded():
    illum, name = moon_illumination(datetime(2026, 8, 29, tzinfo=timezone.utc))
    assert 0 <= illum <= 1
    assert name
    pack = moon_rise_set(22.07, 88.07, datetime(2026, 8, 29, tzinfo=timezone.utc))
    assert pack["phase"]
    assert "source" in pack


def test_usgs_csv_has_error_columns():
    from app.providers.hazards import parse_usgs_csv

    raw = (
        "time,latitude,longitude,depth,mag,magType,nst,gap,dmin,rms,net,id,updated,place,type,"
        "horizontalError,depthError,magError,magNst,status,locationSource,magSource\n"
        "2026-08-27T14:45:48.054Z,33.2423,86.9395,10,5,mb,75,53,11.429,0.85,us,us7000tc9m,"
        "2026-08-27T15:06:59.040Z,western Xizang,earthquake,9.17,1.792,0.053,118,reviewed,us,us\n"
    )
    rows = parse_usgs_csv(raw, 22.07, 88.07)
    assert rows[0]["nst"] == 75
    assert rows[0]["magNst"] == 118
    assert rows[0]["locationSource"] == "us"
    assert rows[0]["horizontalError"] == 9.17


def test_usgs_row_shape():
    from app.providers.hazards import _merge_quakes

    a = [{"mag": 5.1, "time_iso": "t1", "place": "Andaman", "magType": "mb"}]
    b = [{"mag": 5.1, "time_iso": "t1", "place": "Andaman", "source": "EMSC"}]
    merged = _merge_quakes(a, b)
    assert len(merged) == 1
    assert merged[0]["magType"] == "mb"

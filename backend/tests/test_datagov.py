from app.ml.risk import air_quality_risk
from app.providers.datagov import _nearest_station, aqi_category


def test_aqi_category_bands():
    assert aqi_category(21) == "Good"
    assert aqi_category(80) == "Satisfactory"
    assert aqi_category(150) == "Moderate"
    assert aqi_category(250) == "Poor"
    assert aqi_category(450) == "Severe"


def test_aqi_prefers_named_city_over_far_nearest():
    recs = [
        {
            "station": "Ward-32 Bapupara, Siliguri - WBPCB",
            "city": "Siliguri",
            "latitude": "26.7271",
            "longitude": "88.3953",
            "pollutant_id": "OZONE",
            "avg_value": "16",
        },
        {
            "station": "Haldia Municipal, Haldia - WBPCB",
            "city": "Haldia",
            "latitude": "22.0667",
            "longitude": "88.0698",
            "pollutant_id": "PM10",
            "avg_value": "40",
        },
    ]
    name, rows, match = _nearest_station(recs, 22.30, 87.92, "Haldia")
    assert match == "city"
    assert rows[0]["city"] == "Haldia"
    assert "Siliguri" not in name


def test_air_risk_xai_sums():
    card = air_quality_risk(
        {
            "naqi": 25,
            "naqi_pollutants": {"PM10": 25, "NO2": 28, "OZONE": 16, "SO2": 7},
        }
    )
    assert card.id == "air_quality"
    assert sum(f.contribution_pct for f in card.factors) == card.score_pct
    assert "data.gov.in / CPCB" in card.sources


def test_air_risk_uses_overall_naqi_when_pollutants_empty():
    empty = air_quality_risk({"naqi": 300, "naqi_pollutants": {}})
    assert empty.score_pct > 0
    assert sum(f.contribution_pct for f in empty.factors) == empty.score_pct

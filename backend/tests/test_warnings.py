from app.schemas.location import Location
from app.services.snapshot import _warnings


def _loc() -> Location:
    return Location(
        id="in_wb_nadia",
        label="Nadia, West Bengal",
        state="West Bengal",
        district="Nadia",
        lat=23.47,
        lon=88.55,
    )


def test_warnings_multi_hazard_sources():
    caps = [
        {
            "id": "cap1",
            "title": "Heavy Rain Warning for Gangetic West Bengal",
            "body": "Nadia district very heavy rain likely.",
            "published": "Mon, 17 Aug 2026",
        }
    ]
    f = {
        "discharge_trend": "rising",
        "wave_height_m": 3.2,
        "weather_code": 95,
    }
    from datetime import datetime, timezone, timedelta

    quakes = [
        {
            "id": "us7000",
            "mag": 5.1,
            "distance_km": 120,
            "place": "12 km W of Barddhaman",
            "time_iso": (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat(),
        }
    ]
    tsunami = [{"title": "INCOIS: No tsunami threat for Indian coast", "body": "All clear."}]
    naqi = {"value": 312, "category": "Very Poor", "station": "Kalyani", "dominant_pollutant": "PM2.5"}
    out = _warnings(_loc(), caps, 72, f, quakes, tsunami, naqi)
    sources = {w.source for w in out}
    hazards = {w.hazard for w in out}
    assert "imd-cap" in sources
    assert "data.gov.in / CPCB" in sources
    assert "usgs-fdsn" in sources
    assert "incois-itews" not in sources
    assert "open-meteo-marine" in sources
    assert {"weather", "flood", "air", "marine", "seismic"} <= hazards
    assert any(w.severity == "warning" for w in out)


def test_national_severe_included_for_other_state():
    caps = [
        {
            "id": "od1",
            "title": "Extremely heavy rainfall warning — Odisha",
            "body": "Red alert for several Odisha districts.",
            "published": "Mon, 31 Aug 2026",
        }
    ]
    out = _warnings(_loc(), caps, 10, {"weather_code": 1}, [], [], None)
    assert any(w.scope == "india" and "India" in w.title for w in out)
    assert any("rainfall" in (w.title or "").lower() for w in out)


def test_tsunami_threat_is_listed():
    out = _warnings(
        _loc(),
        [],
        10,
        {"weather_code": 1},
        [],
        [{"title": "ITEWS tsunami warning for Andaman", "body": "Threat exists.", "threat": True}],
        None,
    )
    assert any(w.hazard == "tsunami" for w in out)


def test_warnings_quiet_when_nothing_fires():
    out = _warnings(_loc(), [], 20, {"discharge_trend": "steady", "weather_code": 1}, [], [], None)
    assert out == []


def test_incois_catalog_parser():
    from app.providers.hazards import parse_incois_catalog

    data = {
        "datasets": [
            {
                "EVID": "incois2026qcgu",
                "MAGNITUDE": 6.8,
                "REGIONNAME": "Northern Sumatra, Indonesia",
                "ORIGINTIME": "2026-08-15 16:24:00",
                "detail": "https://example.test/b1.json",
            }
        ]
    }
    details = {
        "incois2026qcgu": {
            "bulletinTitle": "... EARTHQUAKE BULLETIN ...",
            "evaluation": "Based on historical earthquake and tsunami data, tsunami threat does not exist for India.",
        }
    }
    rows = parse_incois_catalog(data, details)
    assert rows[0]["threat"] is False
    assert "does not exist" in rows[0]["body"]
    assert "M6.8" in rows[0]["title"]
    threat_rows = parse_incois_catalog(
        data,
        {"incois2026qcgu": {"bulletinTitle": "TSUNAMI WARNING", "evaluation": "Tsunami threat exists for Andaman."}},
    )
    assert threat_rows[0]["threat"] is True

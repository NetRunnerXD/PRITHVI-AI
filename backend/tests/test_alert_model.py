from types import SimpleNamespace

from app.services.snapshot import _warnings
from tests.tabs.isolation import loc as howrah_loc

from app.schemas.location import Location


def _nadia() -> Location:
    return Location(
        id="in_wb_nadia",
        label="Nadia, West Bengal",
        state="West Bengal",
        district="Nadia",
        lat=23.47,
        lon=88.55,
    )


def test_drought_heat_vera_at_pin():
    risks = [
        SimpleNamespace(id="drought", score_pct=80),
        SimpleNamespace(id="heat", score_pct=72),
        SimpleNamespace(id="flood", score_pct=20),
    ]
    vera = {"heat_wave": {"level_key": "watch", "level": "Warning"}, "heavy_rain": {"level_key": "quiet"}}
    out = _warnings(_nadia(), [], 10, {"weather_code": 1}, [], [], None, risks=risks, vera=vera)
    kinds = {w.kind for w in out}
    assert "drought" in kinds
    assert "heatwave" in kinds


def test_scan_assam_flood_on_howrah_pin():
    home = howrah_loc("Howrah")
    hits = [
        {
            "kind": "flood",
            "state": "Assam",
            "title": "Predicted flood warning — Assam (Guwahati)",
            "body": "score 80",
            "lat": 26.14,
            "lon": 91.73,
        }
    ]
    out = _warnings(home, [], 10, {"weather_code": 1}, [], [], None, scan_hits=hits)
    assert any(w.scope == "india" and w.kind == "flood" and "Assam" in w.title for w in out)


def test_official_odisha_rain_suppresses_model_duplicate():
    caps = [
        {
            "id": "od1",
            "title": "Extremely heavy rainfall warning — Odisha",
            "body": "Red alert for several Odisha districts.",
            "published": "Mon, 31 Aug 2026",
            "link": "https://example.test/cap",
        }
    ]
    hits = [
        {
            "kind": "rainfall",
            "state": "Odisha",
            "title": "Predicted very heavy rain — Odisha (Bhubaneswar)",
            "lat": 20.3,
            "lon": 85.8,
        }
    ]
    out = _warnings(_nadia(), caps, 10, {"weather_code": 1}, [], [], None, scan_hits=hits)
    rain = [w for w in out if w.kind == "rainfall" and "Odisha" in (w.title + " ".join(w.states))]
    assert any(w.source == "imd-cap" for w in rain)
    assert not any(w.source == "prithvi-netra" for w in rain)

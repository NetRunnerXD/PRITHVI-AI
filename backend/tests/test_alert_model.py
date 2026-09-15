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


def test_scan_hits_prefers_thunder_over_drought_flood():
    from app.services.alert_scan import _hits

    rows = [
        {
            "state": "West Bengal",
            "name": "Kolkata",
            "lat": 22.5,
            "lon": 88.3,
            "flood_score": 10,
            "drought_score": 90,
            "precip_3d_mm": 1,
            "temp_max_c": 32,
            "thunder_code": 95,
        }
    ]
    hits = _hits(rows)
    kinds = [h["kind"] for h in hits]
    assert "thunderstorm" in kinds
    assert kinds.index("thunderstorm") < kinds.index("drought")


def test_convective_lightning_thunder_cloudburst():
    conv = {
        "lightning": {"level": "watch", "score_pct": 52, "n_strokes": 4, "nearest_km": 12},
        "cloudburst": {"level": "watch", "score_pct": 48},
        "downburst": {"level": "quiet", "score_pct": 12},
    }
    out = _warnings(
        _nadia(),
        [],
        10,
        {"weather_code": 95, "hourly_weather_code": [95, 3]},
        [],
        [],
        None,
        convective=conv,
    )
    kinds = {w.kind for w in out}
    assert "lightning" in kinds
    assert "extreme_rain" in kinds
    assert "cloudburst" not in kinds
    assert "thunderstorm" in kinds


def test_cloudburst_conditions_only_when_qualified():
    conv = {
        "cloudburst": {
            "level": "watch",
            "score_pct": 82,
            "label": "cloudburst_conditions",
            "qualifies": True,
            "eta_min": 20,
        }
    }
    out = _warnings(_nadia(), [], 10, {"weather_code": 1}, [], [], None, convective=conv)
    hits = [w for w in out if w.kind == "cloudburst"]
    assert hits
    assert "conditions" in hits[0].title.lower()
    assert "100" in hits[0].body or "watch" in hits[0].body.lower()


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


def test_segment_halo_is_cloud_layer():
    from app.science.sat_cv import segment

    g = [[255] * 16 for _ in range(16)]
    for y in range(4, 10):
        for x in range(4, 10):
            g[y][x] = 244
    cells = segment(g, bounds=(86.0, 90.0, 21.0, 24.0))
    assert cells
    assert any(c.get("layer") == "anvil" or c.get("kind") == "cloud" for c in cells)


def test_ir_only_lightning_does_not_alert():
    conv = {
        "lightning": {
            "level": "watch",
            "score_pct": 52,
            "n_strokes": 0,
            "gate": {"ok": False, "status": "unverified"},
        }
    }
    out = _warnings(_nadia(), [], 10, {"weather_code": 1}, [], [], None, convective=conv)
    assert "lightning" not in {w.kind for w in out}


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


def test_ledger_pin_warnings(monkeypatch):
    from app.services.alerts import _ledger_pin_warnings

    dummy_rows = [
        {
            "event_id": "evt_123",
            "phase": "live",
            "kind": "thunderstorm",
            "lat": 23.5,
            "lon": 88.6,
            "place": "Nadia",
            "gate": {"ok": True},
            "started_at": "2026-09-14T07:00:00Z",
            "closes_at": "2026-09-14T08:00:00Z",
        }
    ]

    import app.store.hazard_events as he
    monkeypatch.setattr(he, "query", lambda past_h=12: dummy_rows)

    warnings = _ledger_pin_warnings(_nadia())
    assert len(warnings) >= 1
    assert warnings[0].id == "ledger-evt_123"
    assert warnings[0].kind == "thunderstorm"
    assert "Nadia" in warnings[0].title


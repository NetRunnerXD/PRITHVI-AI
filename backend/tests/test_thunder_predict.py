from datetime import datetime, timezone

from app.science.sat_cv import segment
from app.science.thunder_predict import confidence_of, lifetime_min, live_window, predicted_strikes


def test_lifetime_differs_by_physics():
    cold = {
        "kind": "cloudburst",
        "lat": 27.1,
        "lon": 88.5,
        "area_km2": 420,
        "min_tb_k": 208,
        "p_lightning": 0.7,
        "p_cloudburst": 0.6,
        "rain_ir_mm_h": 24,
        "speed_kmh": 8,
        "trend": "growing",
        "cooling_k": 2.2,
    }
    warm = {
        "kind": "cloud",
        "lat": 19.1,
        "lon": 72.9,
        "area_km2": 50,
        "min_tb_k": 246,
        "p_lightning": 0.12,
        "p_cloudburst": 0.08,
        "rain_ir_mm_h": 3,
        "speed_kmh": 38,
        "trend": "collapsing",
        "cooling_k": -0.4,
    }
    mid = {
        "kind": "storm",
        "lat": 23.0,
        "lon": 80.0,
        "area_km2": 140,
        "min_tb_k": 228,
        "p_lightning": 0.35,
        "p_cloudburst": 0.22,
        "rain_ir_mm_h": 10,
        "speed_kmh": 18,
        "trend": "steady",
        "cooling_k": 0.6,
    }
    a, b, c = lifetime_min(cold), lifetime_min(warm), lifetime_min(mid)
    assert a > c > b
    assert abs(a - b) > 8


def test_live_windows_stay_open_and_differ():
    now = datetime(2026, 8, 19, 12, 0, tzinfo=timezone.utc)
    a = live_window(
        {
            "kind": "lightning",
            "lat": 22.57,
            "lon": 88.36,
            "area_km2": 200,
            "min_tb_k": 215,
            "p_lightning": 0.6,
            "trend": "growing",
        },
        now,
    )
    b = live_window(
        {
            "kind": "downburst",
            "lat": 26.2,
            "lon": 91.7,
            "area_km2": 70,
            "min_tb_k": 235,
            "p_lightning": 0.3,
            "trend": "collapsing",
        },
        now,
    )
    assert a["phase"] == "live"
    assert a["closes_ms"] > a["started_ms"]
    assert a["closes_ms"] > int(now.timestamp() * 1000)
    assert a["closes_ms"] != b["closes_ms"]


def test_predicted_strikes_include_weaker_cloud():
    now = datetime(2026, 8, 19, 12, 0, tzinfo=timezone.utc)
    cells = [
        {
            "id": "c9",
            "kind": "cloud",
            "lat": 22.57,
            "lon": 88.36,
            "place": "Kolkata, West Bengal",
            "area_km2": 80,
            "min_tb_k": 244,
            "p_lightning": 0.24,
            "p_cloudburst": 0.08,
            "u_kmh": 10,
            "v_kmh": 0,
            "trend": "steady",
            "ring": [[22.7, 88.2], [22.7, 88.5], [22.4, 88.5], [22.4, 88.2], [22.7, 88.2]],
        }
    ]
    hits, _ = predicted_strikes(cells, now)
    assert hits
    assert all(h["phase"] == "predicted" for h in hits)
    assert any(h["kind"] == "lightning" for h in hits)
    assert any(h["kind"] == "cloud" for h in hits)


def test_area_polygons_are_storm_not_lightning():
    now = datetime(2026, 8, 19, 12, 0, tzinfo=timezone.utc)
    hits, polys = predicted_strikes(
        [
            {
                "id": "c1",
                "kind": "lightning",
                "lat": 22.57,
                "lon": 88.36,
                "p_lightning": 0.5,
                "place": "Kolkata, West Bengal",
                "area_km2": 80,
                "min_tb_k": 220,
                "u_kmh": 12,
                "v_kmh": 4,
                "ring": [[22.7, 88.2], [22.7, 88.5], [22.4, 88.5], [22.4, 88.2], [22.7, 88.2]],
            }
        ],
        now,
    )
    assert hits
    assert polys
    assert all(p["kind"] != "lightning" for p in polys)
    assert all(p.get("label") for p in polys)


def test_live_poly_drops_unmapped_ring():
    now = datetime(2026, 8, 19, 12, 0, tzinfo=timezone.utc)
    _, polys = predicted_strikes(
        [
            {
                "id": "out",
                "kind": "storm",
                "lat": 22.57,
                "lon": 88.36,
                "p_lightning": 0.5,
                "ring": [[2.0, 2.0], [2.0, 8.0], [8.0, 8.0], [8.0, 2.0], [2.0, 2.0]],
            }
        ],
        now,
    )
    assert polys == []


def test_predicted_strikes_skip_without_nwp():
    now = datetime(2026, 8, 19, 12, 0, tzinfo=timezone.utc)
    cells = [
        {
            "id": "ir-only-weak",
            "kind": "lightning",
            "lat": 22.57,
            "lon": 88.36,
            "p_lightning": 0.08,
            "nwp_thunder": False,
            "nwp_thunder_fwd": False,
            "n_strokes": 0,
            "u_kmh": 10,
            "v_kmh": 0,
            "area_km2": 80,
            "min_tb_k": 220,
        }
    ]
    hits, _ = predicted_strikes(cells, now)
    assert not any(h["kind"] == "lightning" and h["phase"] == "predicted" for h in hits)


def test_predicted_strikes_keep_ir_only_above_floor():
    now = datetime(2026, 8, 19, 12, 0, tzinfo=timezone.utc)
    cells = [
        {
            "id": "ir-only",
            "kind": "lightning",
            "lat": 22.57,
            "lon": 88.36,
            "p_lightning": 0.5,
            "nwp_thunder": False,
            "nwp_thunder_fwd": False,
            "n_strokes": 0,
            "u_kmh": 10,
            "v_kmh": 0,
            "area_km2": 80,
            "min_tb_k": 220,
        }
    ]
    hits, _ = predicted_strikes(cells, now)
    assert any(h["kind"] == "lightning" and h["phase"] == "predicted" for h in hits)


def test_predicted_strikes_skip_weak_floor():
    now = datetime(2026, 8, 19, 12, 0, tzinfo=timezone.utc)
    cells = [
        {
            "id": "weak",
            "kind": "cloud",
            "lat": 22.57,
            "lon": 88.36,
            "p_lightning": 0.08,
            "p_cloudburst": 0.05,
            "u_kmh": 8,
            "v_kmh": 0,
            "area_km2": 40,
            "min_tb_k": 250,
        }
    ]
    hits, _ = predicted_strikes(cells, now)
    assert hits == []


def test_predicted_strikes_are_future_and_in_india():
    now = datetime(2026, 8, 19, 12, 0, tzinfo=timezone.utc)
    cells = [
        {
            "id": "c0",
            "kind": "lightning",
            "lat": 22.57,
            "lon": 88.36,
            "place": "Kolkata, West Bengal",
            "area_km2": 180,
            "min_tb_k": 212,
            "p_lightning": 0.72,
            "p_cloudburst": 0.3,
            "u_kmh": 25,
            "v_kmh": 10,
            "trend": "growing",
            "ring": [[22.7, 88.2], [22.7, 88.5], [22.4, 88.5], [22.4, 88.2], [22.7, 88.2]],
        }
    ]
    hits, polys = predicted_strikes(cells, now)
    assert hits
    assert all(h["phase"] == "predicted" for h in hits)
    assert all(h["started_ms"] >= int(now.timestamp() * 1000) for h in hits)
    assert all(68.0 < h["lon"] < 97.4 and 6.6 < h["lat"] < 35.8 for h in hits)
    assert all(p.get("lead_min") == 30 for p in polys)
    assert all(p.get("label") and p.get("place") for p in polys)
    assert any(len(p["ring"]) >= 4 for p in polys)
    assert all("confidence" in h and h["confidence_band"] in {"low", "medium", "high"} for h in hits)
    assert any(h["kind"] == "lightning" for h in hits)


def test_confidence_rises_with_cape_and_agrees():
    weak = confidence_of(0.2, lead_min=60, frames=1, cape=200)
    strong = confidence_of(0.7, lead_min=15, frames=2, cape=2500, weather_code=95, agrees=True, ot=True)
    assert strong["confidence"] > weak["confidence"]
    assert strong["confidence_band"] == "high"
    assert weak["confidence_band"] in {"low", "medium"}


def test_segment_attaches_ring():
    g = [[255] * 16 for _ in range(16)]
    for y in range(6, 12):
        for x in range(6, 12):
            g[y][x] = 214
    cells = segment(g, bounds=(86.0, 90.0, 21.0, 24.0))
    assert cells
    assert cells[0]["ring"]
    assert len(cells[0]["ring"]) >= 4

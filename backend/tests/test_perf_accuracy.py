"""Regression tests for the map-accuracy + speed branch (offline, no network)."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone

import pytest


def test_georef_round_trip_and_known_points():
    from app.providers.imd_insat import Georef, REF_SIZE

    g = Georef.for_size(*REF_SIZE)
    for lat, lon in ((28.61, 77.21), (13.08, 80.27), (34.08, 74.8), (8.5, 76.9)):
        x, y = g.px(lat, lon)
        la, lo = g.latlon(x, y)
        assert abs(la - lat) < 1e-6 and abs(lo - lon) < 1e-6
    # Mercator: 10° of latitude spans more pixels at 30–40°N than at 0–10°N
    _, y0 = g.px(0, 80)
    _, y10 = g.px(10, 80)
    _, y30 = g.px(30, 80)
    _, y40 = g.px(40, 80)
    assert (y30 - y40) > (y0 - y10) * 1.2


def test_cold_ground_veto_high_terrain_and_clear_sky():
    from app.science.storm_map import cold_ground_veto

    ladakh = {"lat": 35.1, "lon": 77.76, "min_tb_k": 245.0}
    assert cold_ground_veto(ladakh, {"elevation_m": 4200, "cloud_cover": 50, "weather_code": 3, "precip_mm": 0}, 30)
    deep = {"lat": 35.1, "lon": 77.76, "min_tb_k": 215.0}
    assert not cold_ground_veto(deep, {"elevation_m": 4200, "cloud_cover": 90, "weather_code": 95, "precip_mm": 3}, 30)
    clear = {"lat": 25.8, "lon": 71.9, "min_tb_k": 240.0}
    assert cold_ground_veto(clear, {"ok": True, "elevation_m": 220, "cloud_cover": 0, "weather_code": 0, "precip_mm": 0}, 40)


def test_gibs_candidate_times_are_real_times_not_midnight():
    from app.providers.gibs_ir import imerg_candidate_times, ir_candidate_times

    now = datetime(2026, 10, 20, 7, 47, tzinfo=timezone.utc)
    ts = ir_candidate_times(now)
    assert ts[0] == "2026-10-20T07:20:00Z" and ts[1] == "2026-10-20T07:10:00Z"
    assert imerg_candidate_times(now)[:2] == ["2026-10-20", "2026-10-19"]


def test_gibs_colormap_decoding():
    from app.providers.gibs_ir import _decode_value

    assert _decode_value((0, 0, 0, 0), "imerg_mm_h") == (False, None)  # transparent = no value
    ok, v = _decode_value((0, 118, 78, 255), "imerg_mm_h")
    assert ok and 0.1 <= v < 0.11
    ok, v = _decode_value((255, 255, 255, 255), "ir_c")
    assert ok and v < -90


def test_ingest_status_stale_is_not_ready(monkeypatch):
    from app.store import ingest_status
    from app.store.time import ms, now_utc

    monkeypatch.setitem(ingest_status._MEM, "ready", True)
    monkeypatch.setitem(ingest_status._MEM, "phase", "ready")
    monkeypatch.setitem(ingest_status._MEM, "started_ms", ms(now_utc()) - 7 * 24 * 3600 * 1000)
    snap = ingest_status.snapshot()
    assert snap["ready"] is False and snap["stale"] is True and "stale" in snap["message"]


def test_pn_blend_weights_and_persistence_fallback():
    from app.science.pn.blend import blend

    now = datetime(2026, 10, 20, 6, 0, tzinfo=timezone.utc)
    # Open-Meteo style IST local hourly strings
    times = [f"2026-10-20T{h:02d}:00" for h in range(11, 24)]
    models = {
        "gfs": {"utc_offset_seconds": 19800, "hourly": {"time": times, "precipitation": [2.0] * len(times)}},
        "ifs025": {"utc_offset_seconds": 19800, "hourly": {"time": times, "precipitation": [0.0] * len(times)}},
    }
    nc = {
        "hours": [{"lead_h": L, "mm": 4.0} for L in range(1, 7)],
        "observed": [{"t": "2026-10-20T11:00", "mm": 4.0}],  # IST → 05:30Z, 0.5 h old
    }
    out = blend(nc, models, now=now)
    h1 = out["hours"][0]
    # lead 1 research weights: extrap .7 / gfs .1 / ifs .2 → 0.7*4 + 0.1*2 + 0 = 3.0
    assert h1["lead_h"] == 1 and abs(h1["mm"] - 3.0) < 1e-6
    stale = blend({"hours": nc["hours"], "observed": [{"t": "2026-10-19T20:00", "mm": 4.0}]}, models, now=now)
    assert stale["extrap_source"].startswith("persistence")


def test_cyclone_categories():
    from app.providers.cyclones import imd_category, ss_category

    assert imd_category(30) == "DD" and imd_category(70) == "VSCS" and imd_category(125) == "SuCS"
    assert ss_category(140) == "Cat 5" and ss_category(40) == "TS"


def test_cyclone_geometry_parse_splits_observed_and_forecast():
    from app.providers.cyclones import parse_geometry

    circ = lambda la, lo: [[[lo - 0.1, la], [lo + 0.1, la], [lo, la + 0.1], [lo - 0.1, la]]]  # noqa: E731
    base = {"polygondate": "2026-10-19T12:00:00"}
    geo = {
        "features": [
            {"properties": {**base, "Class": "Point_Polygon_Point_0", "key": "10190000"}, "geometry": {"type": "Polygon", "coordinates": circ(14.0, 138.0)}},
            {"properties": {**base, "Class": "Point_Polygon_Point_1", "key": "10191200"}, "geometry": {"type": "Polygon", "coordinates": circ(14.8, 137.6)}},
            {"properties": {**base, "Class": "Point_Polygon_Point_2", "key": "10200000"}, "geometry": {"type": "Polygon", "coordinates": circ(15.9, 135.5)}},
            {"properties": {**base, "Class": "Line_Line_0", "polygonlabel": "HU", "forecast": False}, "geometry": {"type": "LineString", "coordinates": [[138.0, 14.03], [137.6, 14.8]]}},
            {"properties": {**base, "Class": "Poly_Cones"}, "geometry": {"type": "Polygon", "coordinates": circ(15, 136)}},
        ]
    }
    out = parse_geometry(geo)
    assert len(out["observed"]) == 2 and len(out["forecast"]) == 1
    assert out["forecast"][0]["t"] == "2026-10-20T00:00:00Z" and out["cone"]


def test_cv_motion_keyed_to_image_time(tmp_path, monkeypatch):
    from app.science import cv_nowcast

    store: dict = {}
    monkeypatch.setattr(cv_nowcast, "_load", lambda: dict(store))
    monkeypatch.setattr(cv_nowcast, "_save", lambda d: (store.clear(), store.update(d)))
    grid = [[290.0] * 20 for _ in range(20)]
    cv_nowcast.enhance([], grid, (68, 97.5, 6.5, 37.2), image_time="2026-10-20T06:00:00+00:00")
    _, meta = cv_nowcast.enhance([], grid, (68, 97.5, 6.5, 37.2), image_time="2026-10-20T06:00:00+00:00")
    assert meta["frames"] == 1  # same picture twice → no fake motion
    _, meta2 = cv_nowcast.enhance([], grid, (68, 97.5, 6.5, 37.2), image_time="2026-10-20T06:30:00+00:00")
    assert meta2["frames"] == 2 and meta2["dt_min"] == 30.0


def test_json_error_keeps_cors_header():
    from fastapi.testclient import TestClient

    from app.config import get_settings
    from app.main import app

    s = get_settings()
    origin = "https://example.org" if s.cors_allow_all else (s.cors_origin_list or ["http://localhost:3000"])[0]

    @app.get("/api/__boom_test")
    async def _boom():
        raise RuntimeError("x")

    c = TestClient(app, raise_server_exceptions=False)
    r = c.get("/api/__boom_test", headers={"Origin": origin})
    assert r.status_code == 500 and r.json()["error"] == "internal_error"
    assert r.headers.get("access-control-allow-origin")

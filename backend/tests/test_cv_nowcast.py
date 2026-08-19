from app.providers.lightning_feed import parse_rows
from app.providers.om_thunder import past_strikes
from app.providers.weatherbit_lightning import parse_payload
from app.science.cv_nowcast import block_flow, cloudburst_prob, cooling_stats, enhance, lightning_prob


def _grid(tb: float, n: int = 16) -> list[list[float]]:
    return [[tb] * n for _ in range(n)]


def test_cooling_and_jump():
    prev = _grid(240)
    curr = _grid(228)
    for y in range(6, 10):
        for x in range(6, 10):
            curr[y][x] = 210
    st = cooling_stats(prev, curr)
    assert st["d_tb"] > 0
    assert st["n_ot"] >= 1


def test_block_flow_shifts_east():
    prev = _grid(260)
    curr = _grid(260)
    for y in range(4, 8):
        for x in range(2, 6):
            prev[y][x] = 220
        for x in range(4, 8):
            curr[y][x] = 220
    dx, dy = block_flow(prev, curr, step=4)
    assert isinstance(dx, float)


def test_probs_rise_for_ot_and_hills():
    cell = {"min_tb_k": 208, "ot": True, "rain_ir_mm_h": 22, "speed_kmh": 8, "trend": "growing"}
    cool = {"d_tb": 2.0, "jump": 3}
    assert lightning_prob(cell, cool, 8) > 0.45
    assert cloudburst_prob(cell, cool, "orographic") > cloudburst_prob(cell, cool, "arid")


def test_lightning_feed_parses_geojson_and_list():
    rows = parse_rows(
        {
            "features": [
                {"geometry": {"coordinates": [88.3, 22.5]}, "properties": {"time": "2026-08-19T10:00:00Z"}},
            ]
        }
    )
    assert rows[0]["lat"] == 22.5
    assert rows[0]["lon"] == 88.3
    flat = parse_rows({"lightning": [{"lat": 13.1, "lon": 80.2, "t": "x"}]})
    assert len(flat) == 1


def test_weatherbit_history_payload_is_past():
    pack = parse_payload(
        {
            "lightning": [
                {
                    "lat": 13.08,
                    "lon": 80.27,
                    "timestamp_utc": "2026-08-19T10:00:00",
                    "past_mins": 40,
                    "distance_km": 12,
                    "type": "flash",
                }
            ]
        },
        13.08,
        80.27,
    )
    assert pack["n"] == 1
    assert pack["strokes"][0]["phase"] == "past"
    assert pack["strokes"][0]["kind"] == "lightning"
    assert pack["strokes"][0]["past_mins"] == 40


def test_om_past_strikes_only_negative_lead():
    pack = {
        "hours": [
            {"lead_h": -2, "thunder": True, "time": "2026-08-19T16:00", "weather_code": 95},
            {"lead_h": 0, "thunder": True, "time": "2026-08-19T18:00", "weather_code": 95},
            {"lead_h": 1, "thunder": True, "time": "2026-08-19T19:00", "weather_code": 95},
            {"lead_h": -1, "thunder": False, "time": "2026-08-19T17:00", "weather_code": 3},
        ]
    }
    rows = past_strikes(13.08, 80.27, pack)
    assert len(rows) == 1
    assert rows[0]["phase"] == "past"
    assert rows[0]["lat"] == 13.08


def test_enhance_tags_cells():
    g = _grid(255, 20)
    for y in range(8, 14):
        for x in range(8, 14):
            g[y][x] = 212
    from app.science.sat_cv import segment

    cells = segment(g, bounds=(68.0, 97.5, 6.5, 37.2))
    out, meta = enhance(cells, g, (68.0, 97.5, 6.5, 37.2))
    assert meta["frames"] >= 1
    if out:
        assert "p_lightning" in out[0]
        assert "p_cloudburst" in out[0]

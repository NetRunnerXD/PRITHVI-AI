from app.providers.gdacs import parse_events


def test_parse_skips_empty():
    assert parse_events([]) == []


def test_parse_caps_twelve():
    rows = [
        {"eventtype": "TS", "latitude": 10 + i * 0.1, "longitude": 80, "name": f"e{i}", "eventid": str(i)}
        for i in range(20)
    ]
    assert len(parse_events(rows)) == 12

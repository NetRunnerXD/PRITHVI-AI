from app.providers.gdacs import parse_events


def test_parse_skips_empty():
    assert parse_events([]) == []


def test_parse_drops_se_asia():
    rows = [
        {"eventtype": "TC", "latitude": 14.6, "longitude": 121.0, "name": "Manila", "country": "Philippines", "eventid": "1"},
        {"eventtype": "FL", "latitude": 26.2, "longitude": 91.7, "name": "Assam", "country": "India", "eventid": "2"},
    ]
    out = parse_events(rows)
    assert all("philippines" not in (r["title"] or "").lower() for r in out)
    assert any("assam" in (r["title"] or "").lower() for r in out)


def test_parse_caps_twelve():
    rows = [
        {"eventtype": "TS", "latitude": 10 + i * 0.1, "longitude": 80, "name": f"e{i}", "eventid": str(i)}
        for i in range(20)
    ]
    assert len(parse_events(rows)) == 12

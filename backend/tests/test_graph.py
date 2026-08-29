from app.agents.graph import route


def test_pump_tonight_activates_nowcast():
    needs, peak = route("should I run the pump tonight in Haldia", ["nowcast"])
    assert "nowcast" in needs
    assert peak >= 0.45


def test_aqi_seeds_quality_neighbor():
    needs, peak = route("AQI in Jaipur", ["aqi"])
    assert "aqi" in needs
    assert peak >= 0.45

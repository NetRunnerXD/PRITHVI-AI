from app.agents.claims import check_claims


def test_replaces_unbound_numeral_keeps_sentence():
    text, bad = check_claims("Rain will dump 81.3 mm on Tuesday in Haldia.", [{"total_mm": 12.2}])
    assert "81.3" not in text
    assert "—" in text
    assert "Haldia" in text
    assert "81.3" in bad


def test_keeps_tool_number():
    text, bad = check_claims("The window total is 12.2 mm.", [{"total_mm": 12.2}])
    assert "12.2" in text
    assert bad == []

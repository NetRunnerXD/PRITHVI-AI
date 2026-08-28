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


def test_keeps_iso_dates_from_payload():
    payload = {
        "forecast": {
            "outlook_days": [{"date": "2026-08-28", "precip_mm": 4.2, "temp_max_c": 32.0}],
            "temp_c": 29.4,
        }
    }
    text, bad = check_claims(
        "Howrah 2026-08-28: 4.2 mm, tmax 32.0°C, now 29.4°C.",
        [payload],
    )
    assert "2026-08-28" in text
    assert "—" not in text
    assert "4.2" in text
    assert "29.4" in text
    assert bad == []


def test_contradiction_unbound_still_blanked():
    text, bad = check_claims(
        "Howrah 2026-08-28 will dump 81.3 mm.",
        [{"outlook_days": [{"date": "2026-08-28", "precip_mm": 4.2}]}],
    )
    assert "2026-08-28" in text
    assert "81.3" not in text
    assert "—" in text
    assert "81.3" in bad

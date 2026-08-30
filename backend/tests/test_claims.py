from app.agents.claims import check_claims


def test_replaces_unbound_numeral_keeps_sentence():
    text, bad = check_claims("Rain will dump 81.3 mm on Tuesday in Haldia.", [{"total_mm": 12.2}])
    assert "81.3" not in text
    assert "—" in text
    assert "Haldia" in text
    assert "81.3" in bad


def test_window_day_not_blanked_in_month_name():
    text, bad = check_claims(
        "For 30 August 2026 at Haldia, rain is 2.7 mm.",
        [{"need": "rain_window", "start": "2026-08-30", "end": "2026-08-30", "days": [{"date": "2026-08-30", "precip_mm": 2.7}]}],
        window={"start": "2026-08-30", "end": "2026-08-30"},
    )
    assert "30" in text
    assert "—" not in text
    assert "2.7" in text
    assert bad == []


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


def test_single_day_window_does_not_license_3d_total():
    text, bad = check_claims(
        "Tomorrow will see 18 mm over 3 days.",
        [
            {
                "need": "forecast",
                "precip_next_3d_mm": 18.0,
                "outlook_days": [{"date": "2026-08-29", "precip_mm": 4.2}],
            }
        ],
        window={"start": "2026-08-29", "end": "2026-08-29"},
    )
    assert "18" not in text or "—" in text
    assert "18" in bad or "18.0" in bad or "—" in text


def test_contradiction_unbound_still_blanked():
    text, bad = check_claims(
        "Howrah 2026-08-28 will dump 81.3 mm.",
        [{"outlook_days": [{"date": "2026-08-28", "precip_mm": 4.2}]}],
    )
    assert "2026-08-28" in text
    assert "81.3" not in text
    assert "—" in text
    assert "81.3" in bad

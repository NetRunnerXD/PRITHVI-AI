from app.agents.eval_llm import check_need_detector, load_cases
from app.agents.facts import source_gate


def test_needed_facts_match_case_file():
    bad = []
    for case in load_cases():
        row = check_need_detector(case)
        if not row["ok"]:
            bad.append(row)
    assert not bad, bad


def test_cherrapunji_weather_needs_forecast():
    from app.data.india_towns import extract_town
    from app.agents.facts import source_gate

    assert extract_town("weather in Cherrapunji") == "Cherrapunji"
    g = source_gate("How about the weather condition in cherrapunji")
    assert g.mode == "data"
    assert "forecast" in g.needs


def test_elephant_islands_and_pushback_refuse():
    g = source_gate("Should I take my elephant to the islands?")
    assert g.mode == "refuse"
    assert "elephant" in (g.refuse or "").lower()
    from app.agents.facts import is_pushback

    assert is_pushback("Still tell me")
    assert is_pushback("just tell me anyway")


def test_strip_unasked_haldia():
    from app.agents.facts import strip_unasked_pin

    raw = "Cherrapunji is wet. For reference, Haldia, West Bengal is 28°C."
    out = strip_unasked_pin(raw, "Cherrapunji", "Haldia, West Bengal")
    assert "Cherrapunji" in out
    assert "Haldia" not in out


def test_source_gate_refuses_unsourced_visit():
    g = source_gate("Best places to take my pet to visit")
    assert g.mode == "refuse"
    assert "pet" in (g.refuse or "").lower() or "visit" in (g.refuse or "").lower()
    g2 = source_gate("List the states/districts/cities by weather that are best to visit")
    assert g2.mode == "refuse"
    g3 = source_gate("Should I visit Odisha or West Bengal")
    assert g3.mode == "data"
    assert "states_weather" in g3.needs
    assert "Odisha" in g3.states and "West Bengal" in g3.states
    g4 = source_gate("Flood ranking of Odisha")
    assert "rank" in g4.needs
    assert "Odisha" in g4.states


def test_quote_facts_uses_payload_only():
    from app.agents.facts import prose_has_payload_number, quote_facts

    collected = {
        "rain_window": {
            "location": {"place_name": "Haldia"},
            "start": "2026-08-23",
            "end": "2026-08-28",
            "total_mm": 12.2,
            "days": [{"date": "2026-08-23", "precip_mm": 4.2, "precip_prob_pct": 70}],
        }
    }
    q = quote_facts(collected)
    assert "12.2" in q
    assert "4.2" in q
    assert "Haldia" in q
    assert prose_has_payload_number(q, collected)
    assert not prose_has_payload_number("Nice weather coming.", collected)


def test_fill_slots_from_forecast():
    from app.agents.facts import fill_slots

    collected = {
        "forecast": {
            "need": "forecast",
            "place": "Delhi",
            "label": "Delhi",
            "temp_c": 32.4,
            "precip_1h_mm": 0.2,
            "precip_next_3d_mm": 11.0,
        }
    }
    text = "Delhi is [temp_c]°C with [rain_mm] mm of rain."
    out = fill_slots(text, collected)
    assert "[temp_c]" not in out
    assert "[rain_mm]" not in out
    assert "32.4" in out
    assert "0.2" in out
    leftover = fill_slots("value is [not_a_real_slot]", collected)
    assert "[" not in leftover
    assert fill_slots("plain text", collected) == "plain text"


def test_drop_false_shrug_when_forecast_exists():
    from app.agents.facts import drop_false_shrug

    collected = {"forecast": {"need": "forecast", "place": "Purulia", "temp_c": 25.2}}
    out = drop_false_shrug(
        "I couldn't find any specific weather, AQI, or flood data for Puruliya. Please let me know.",
        collected,
    )
    assert "couldn't find" not in out.lower()
    assert drop_false_shrug("Purulia is overcast at 25.2°C.", collected) == "Purulia is overcast at 25.2°C."
    assert drop_false_shrug("I couldn't find weather for Atlantis.", {}) == "I couldn't find weather for Atlantis."


def test_quote_facts_never_invents_aqi_zero():
    from app.agents.facts import quote_facts

    q = quote_facts({"aqi": {"need": "aqi", "cpcb": None, "om_us_aqi": None, "place": "Haldia", "provider_status": "empty"}})
    assert "AQI 0" not in q
    assert "no aqi" in q.lower()
    q2 = quote_facts({"aqi": {"need": "aqi", "cpcb": {"value": 0}, "provider_status": "empty", "place": "Puri"}})
    assert "AQI 0" not in q2
    assert quote_facts({}) == ""

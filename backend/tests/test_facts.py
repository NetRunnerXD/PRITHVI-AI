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


def test_strip_foreign_places_drops_default_pin():
    from app.agents.facts import strip_foreign_places

    raw = "Howrah is cloudy. Haldia has 40 mm this week."
    out = strip_foreign_places(raw, ["Howrah"], ["Haldia"])
    assert "Howrah" in out
    assert "Haldia" not in out


def test_strip_foreign_places_drops_bihar_when_focus_is_howrah():
    from app.agents.facts import strip_foreign_places

    raw = (
        "Howrah is 26.4°C with 50.7 mm in 3 days. "
        "The forecast for Patna district of Bihar shows a thunderstorm."
    )
    out = strip_foreign_places(raw, ["Howrah", "West Bengal"], ["Patna", "Bihar"])
    assert "Howrah" in out
    assert "26.4" in out
    assert "Patna" not in out
    assert "Bihar" not in out


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


def test_quote_facts_rank_once_no_india_when_state_rank_present():
    from app.agents.facts import quote_facts

    collected = {
        "rank": {
            "need": "rank",
            "state": "West Bengal",
            "metric": "flood",
            "ranked": [
                {"district": "South 24 Parganas", "flood_score": 73, "precip_3d_mm": 52.6},
                {"district": "Purulia", "flood_score": 72, "precip_3d_mm": 51.3},
            ],
        },
        "rank:West Bengal": {
            "need": "rank",
            "state": "West Bengal",
            "metric": "flood",
            "ranked": [
                {"district": "South 24 Parganas", "flood_score": 73, "precip_3d_mm": 52.6},
                {"district": "Purulia", "flood_score": 72, "precip_3d_mm": 51.3},
            ],
        },
        "states_weather": {
            "metric": "flood",
            "ranked": [{"state": "Chhattisgarh", "district": "Raipur", "flood_score": 86, "precip_3d_mm": 171.2, "temp_max_c": 30}],
        },
    }
    q = quote_facts(collected)
    assert q.count("South 24 Parganas") == 1
    assert "Chhattisgarh" not in q
    assert "1." in q
    assert "rank 1:" not in q


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


def test_quote_facts_single_day_does_not_lead_with_3d():
    from app.agents.facts import quote_facts

    collected = {
        "rain_window": {
            "location": {"place_name": "Haldia"},
            "start": "2026-08-29",
            "end": "2026-08-29",
            "total_mm": 4.2,
            "days": [{"date": "2026-08-29", "precip_mm": 4.2}],
        },
        "forecast": {
            "place": "Haldia",
            "precip_next_3d_mm": 18.0,
            "precip_7d_mm": 40.0,
            "outlook_days": [
                {"date": "2026-08-29", "precip_mm": 4.2, "temp_max_c": 32},
                {"date": "2026-08-30", "precip_mm": 9.0},
            ],
        },
    }
    q = quote_facts(collected, window={"start": "2026-08-29", "end": "2026-08-29"})
    assert "4.2" in q
    assert "next 3 days" not in q
    assert "7 days" not in q
    assert "2026-08-30" not in q


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


def test_dash_soup_from_stripped_outlook():
    from app.agents.facts import is_dash_soup

    soup = (
        "August —: Partly cloudy with a high chance of rain (—%), "
        "temperature ranging from —°C to —°C. The total is — mm."
    )
    assert is_dash_soup(soup)
    assert not is_dash_soup("Malda now: 25.2°C, this hour 0 mm (Open-Meteo).")


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

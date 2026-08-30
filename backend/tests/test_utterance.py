"""Utterance planner: every class of human line and its contradiction."""

from app.agents.data_tool import parse_text_call, strip_tool_syntax
from app.agents.facts import source_gate
from app.agents.utterance import extract_asked_span, interpret, looks_like_bare_place


def test_tomorrow_is_not_a_place():
    from app.agents.utterance import extract_asked_span, interpret, is_time_followup, looks_like_bare_place

    assert extract_asked_span("forecast for tomorrow") is None
    assert extract_asked_span("and tomorrow") is None
    assert extract_asked_span("what about tomorrow") is None
    assert not looks_like_bare_place("tomorrow")
    assert not looks_like_bare_place("and tomorrow")
    assert is_time_followup("and tomorrow")
    assert is_time_followup("what about tomorrow")
    p = interpret("and tomorrow")
    assert p.follow
    assert p.asked is None or p.asked.lower() != "tomorrow"
    assert "rain_window" in p.needs
    p2 = interpret("forecast for tomorrow")
    assert p2.asked is None or p2.asked.lower() != "tomorrow"
    p3 = interpret("How much rain tomorrow in Haldia?")
    assert p3.asked and p3.asked.lower() == "haldia"


def test_extract_spans():
    assert extract_asked_span("Puruliya") == "Puruliya"
    assert extract_asked_span("weather in Puruliya").lower() in {"puruliya", "purulia"}
    assert extract_asked_span("Atlantis weather").lower() == "atlantis"
    assert extract_asked_span("How about the weather condition in cherrapunji").lower() == "cherrapunji"
    assert extract_asked_span("How much rain tomorrow in Haldia").lower() == "haldia"
    how_much = extract_asked_span("How much rain is expected this week?")
    assert how_much is None or how_much.lower() not in {"how", "how much", "much"}
    assert extract_asked_span("in the next 2 hours") is None or extract_asked_span("in the next 2 hours").lower() != "the next"


def test_contradiction_how_about_is_not_a_place():
    """If Cherrapunji extraction works, 'How about' must not become the asked place."""
    assert extract_asked_span("How about the weather condition in cherrapunji").lower() != "how about"
    p = interpret("How much rain tomorrow in Haldia?")
    assert p.mode == "data"
    assert p.asked and p.asked.lower() != "how much"


def test_weather_known_vs_unknown():
    known = interpret("How about the weather condition in cherrapunji")
    assert known.mode == "data"
    assert "forecast" in known.needs
    unknown = interpret("How about the weather condition in Hogwarts")
    assert unknown.mode == "refuse"


def test_offtopic_stays_chat():
    for q in ("hello there", "Write a short poem about monsoon clouds", "What is 17 times 19?"):
        p = interpret(q)
        assert p.mode == "chat", q
        assert p.needs == []


def test_contradiction_poem_about_purulia_is_not_forecast():
    """A poem request is chat even if a place word appears in the topic list elsewhere."""
    p = interpret("Write a short poem about monsoon clouds")
    assert p.mode == "chat"
    wx = interpret("weather in Purulia")
    assert wx.mode == "data"


def test_pet_and_pushback_topics():
    p = interpret("Should I take my elephant to the islands?")
    assert p.mode == "refuse"
    assert "elephant" in (p.refuse or "").lower()
    visit = interpret("Best places to take my pet to visit")
    assert visit.mode == "refuse"


def test_wb_flood_list_is_rank_not_india_hq():
    p = interpret("Which districts in West Bengal are more likely to get flooded? List them.")
    assert p.mode == "data"
    assert "rank" in p.needs
    assert "states_weather" not in p.needs
    assert "West Bengal" in p.states
    assert "mandi" not in p.needs


def test_rank_and_compare_still_data():
    r = interpret("Flood ranking of Odisha")
    assert r.mode == "data"
    assert "rank" in r.needs
    assert "Odisha" in r.states
    c = interpret("Should I visit Odisha or West Bengal")
    assert c.mode == "data"
    assert "states_weather" in c.needs


def test_garbage_and_punctuation():
    g = interpret("asdfghjkl")
    assert g.mode == "data"
    assert g.needs_geocode
    q = interpret("???")
    assert q.mode in {"chat", "refuse", "data"}
    n = interpret("12345")
    assert n.mode in {"chat", "refuse", "data"}


def test_leaked_data_call_is_parsed_and_stripped():
    args = parse_text_call("data(need=rain_window, place=Haldia).")
    assert args is not None
    assert args["need"] == "rain_window"
    assert args["place"] == "Haldia"
    assert strip_tool_syntax("data(need=rain_window, place=Haldia).") == ""
    assert "Haldia" in strip_tool_syntax("Haldia looks wet.\ndata(need=forecast, place=Haldia)")


def test_fly_plane_tomorrow_is_weather():
    p = interpret("can I fly my plane tomorrow?")
    assert p.mode == "data"
    assert "rain_window" in p.needs or "forecast" in p.needs


def test_outdoor_and_place_time_fragments():
    p = interpret("Can I go for sky diving tomorrow?")
    assert p.mode == "data"
    assert "rain_window" in p.needs or "forecast" in p.needs
    assert not p.asked or "div" not in p.asked.lower()
    p2 = interpret("In Haldia tomorrow at 10 am")
    assert p2.mode == "data"
    assert p2.asked and p2.asked.lower() == "haldia"
    assert "rain_window" in p2.needs
    assert extract_asked_span("In Haldia tomorrow at 10 am").lower() == "haldia"
    refuse = interpret("Can I take my elephant to the islands?")
    assert refuse.mode == "refuse"
    hi = interpret("Hi")
    assert hi.mode == "chat"
    assert hi.needs == []


def test_pin_only_weather_still_fetches():
    for q, need in (
        ("What's the weather today?", "forecast"),
        ("Should I irrigate?", "nowcast"),
        ("Will it rain today?", "rain_window"),
    ):
        p = interpret(q)
        assert p.mode == "data", q
        assert need in p.needs, (q, p.needs)
        assert not p.asked


def test_source_gate_matches_interpret():
    for q in ("Puruliya", "Puri", "Atlantis", "hello there", "AQI in Jaipur"):
        g = source_gate(q)
        p = interpret(q)
        assert g.mode == p.mode
        assert g.needs == p.needs

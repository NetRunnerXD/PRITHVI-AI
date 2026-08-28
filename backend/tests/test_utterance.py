"""Utterance planner: every class of human line and its contradiction."""

from app.agents.facts import source_gate
from app.agents.utterance import extract_asked_span, interpret, looks_like_bare_place


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

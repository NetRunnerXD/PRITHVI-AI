"""Fictitious and foreign names must refuse, never invent, never become Haldia."""

import pytest

from app.agents.utterance import interpret, is_blocked_name, unknown_refuse
from app.services.location_svc import resolve_named_place


FICTION = [
    "Atlantis",
    "Wakanda",
    "Hogwarts",
    "Narnia",
    "Mordor",
    "Gondor",
    "Asgard",
    "Gotham",
    "Westeros",
    "Springfield",
    "Neverland",
    "Camelot",
    "Rivendell",
]
FOREIGN = [
    "Paris",
    "London",
    "Tokyo",
    "New York",
    "Beijing",
    "Dubai",
    "Singapore",
]


@pytest.mark.parametrize("name", FICTION + FOREIGN)
def test_gazetteer_miss_for_non_india(name):
    assert resolve_named_place(name) is None
    assert is_blocked_name(name)


@pytest.mark.parametrize("name", FICTION)
def test_bare_fiction_refuses(name):
    plan = interpret(name)
    assert plan.mode == "refuse"
    assert plan.unknown_place or is_blocked_name(name)
    assert "invent" in (plan.refuse or "").lower() or "gazetteer" in (plan.refuse or "").lower()
    assert "Haldia" not in (plan.refuse or "")


@pytest.mark.parametrize("name", FICTION[:5] + ["Paris", "London"])
def test_weather_in_fiction_refuses(name):
    plan = interpret(f"weather in {name}")
    assert plan.mode == "refuse"
    assert "forecast" not in plan.needs
    assert "Haldia" not in (plan.refuse or "")


def test_contradiction_howrah_is_real_hogwarts_is_not():
    real = interpret("weather in Howrah")
    fake = interpret("weather in Hogwarts")
    assert real.mode == "data"
    assert "forecast" in real.needs
    assert fake.mode == "refuse"
    assert resolve_named_place("Howrah") is not None
    assert resolve_named_place("Hogwarts") is None


def test_contradiction_nadia_is_real_narnia_is_not():
    assert interpret("Nadia").mode == "data"
    assert interpret("Narnia").mode == "refuse"


def test_unknown_refuse_names_the_span():
    msg = unknown_refuse("Atlantis")
    assert "Atlantis" in msg
    assert "Rituchakra" in msg


def test_contradiction_paris_weather_is_not_patna():
    """Foreign real cities stay refused — they must not snap to a similar Indian name."""
    assert resolve_named_place("Paris") is None
    assert resolve_named_place("Patna") is not None
    p = interpret("weather in Paris")
    assert p.mode == "refuse"
    assert p.asked and p.asked.lower() == "paris"

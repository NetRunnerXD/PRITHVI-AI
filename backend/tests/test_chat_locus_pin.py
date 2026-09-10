"""Chat must stay on the dashboard pin for 'in my area' — never geocode 'area'."""

import pytest

from app.agents.layer1_parser import fast_parse_entities
from app.agents.utterance import interpret
from app.data.closed_class import is_closed_query
from app.data.india_districts import match_states


def test_my_area_is_not_a_place():
    assert is_closed_query("area")
    assert is_closed_query("my area")
    assert fast_parse_entities("When will rainfall occur today in my area?")[2] is None
    p = interpret("When will rainfall occur today in my area?")
    assert p.asked is None
    assert not p.needs_geocode


def test_starters_do_not_match_jharkhand():
    for q in (
        "When will rainfall occur today in my area?",
        "Is the air bad for my kids right now, and what should we do?",
        "What is today's weather outlook and conditions for travel and outdoor activities?",
    ):
        assert "Jharkhand" not in match_states(q)
        assert interpret(q).asked is None


@pytest.mark.asyncio
async def test_orchestrator_keeps_haldia_pin_for_my_area(monkeypatch):
    from app.agents import orchestrator
    from app.llm import ollama_client
    from app.schemas.chat import ChatRequest
    from app.services.location_svc import resolve_named_place

    loc = resolve_named_place("Haldia")
    assert loc and loc.state == "West Bengal"

    async def fake_ping():
        return True, "qwen2.5"

    async def fake_chat(messages, tools=None):
        return {"content": "Rain is possible later today. Carry a light cover.", "tool_calls": [], "tools_stripped": False}

    async def boom_geo(q):
        raise AssertionError(f"must not geocode {q!r}")

    monkeypatch.setattr(ollama_client, "ping", fake_ping)
    monkeypatch.setattr(ollama_client, "chat", fake_chat)
    monkeypatch.setattr("app.agents.orchestrator.resolve_india_place", boom_geo)

    payload = ChatRequest(message="When will rainfall occur today in my area?", location=loc)
    final = None
    async for ev in orchestrator.run_agent(payload):
        if ev.get("type") == "meta" and ev.get("location"):
            assert "Jharkhand" not in str(ev["location"].get("state") or "")
            assert ev["location"].get("place_name") == "Haldia" or "Haldia" in (ev["location"].get("label") or "")
        if ev.get("type") == "final":
            final = ev["message"]
    assert final

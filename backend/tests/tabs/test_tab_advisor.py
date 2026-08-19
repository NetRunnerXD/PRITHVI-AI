"""Advisor tab: How about Malda fetches Malda; Howrah chat does not quote Chhattisgarh."""

import pytest

from app.agents.facts import is_dash_soup, quote_facts
from app.agents.utterance import interpret, is_place_retarget
from app.schemas.chat import ChatRequest
from app.services.location_svc import resolve_location
from .isolation import loc


def test_how_about_malda_is_a_forecast():
    assert is_place_retarget("How about malda")
    p = interpret("How about malda")
    assert p.mode == "data"
    assert "forecast" in p.needs
    assert p.asked and "malda" in p.asked.lower()


def test_contradiction_how_about_a_joke_is_chat():
    p = interpret("How about a joke")
    assert p.mode != "data" or "forecast" not in p.needs


def test_contradiction_what_about_kerala_is_not_a_capital_forecast():
    """State follow-up stays chat so a prior rank can attach — Malda still forecasts."""
    p = interpret("what about Kerala?")
    assert "forecast" not in p.needs
    assert interpret("How about malda").needs == ["forecast"]


@pytest.mark.asyncio
async def test_malda_dash_soup_replaced_with_quoted_facts(monkeypatch):
    from app.agents import orchestrator
    from app.llm import ollama_client

    soup = (
        "August —: Partly cloudy with a high chance of rain (—%), "
        "temperature ranging from —°C to —°C. "
        "The total precipitation over the next week is expected to be around — mm. "
        "I only quote figures from Rituchakra data."
    )

    async def fake_ping():
        return True, "qwen2.5"

    async def fake_chat(messages, tools=None):
        return {
            "content": (
                "August 19: Partly cloudy with a high chance of rain (80%), "
                "temperature ranging from 24°C to 33°C. Total 91.3 mm."
            ),
            "tool_calls": [],
            "tools_stripped": False,
        }

    async def fake_call(self, args):
        locn = self.loc
        return {
            "need": "forecast",
            "place": locn.place_name or locn.district,
            "label": locn.label,
            "temp_c": 27.1,
            "precip_1h_mm": 0.0,
            "precip_next_3d_mm": 11.2,
            "precip_7d_mm": 22.0,
            "outlook_days": [
                {"date": "2026-08-19", "precip_mm": 4.2, "precip_prob_pct": 70, "temp_max_c": 32.0, "temp_min_c": 25.0}
            ],
        }

    monkeypatch.setattr(ollama_client, "ping", fake_ping)
    monkeypatch.setattr(ollama_client, "chat", fake_chat)
    monkeypatch.setattr("app.agents.data_tool.DataLib.call", fake_call)

    events = []
    async for ev in orchestrator.run_agent(
        ChatRequest(message="How about malda", location=resolve_location(q="Haldia"))
    ):
        events.append(ev)
    body = next(e for e in events if e["type"] == "final")["message"].get("content_en") or ""
    assert "Malda" in body
    assert "Haldia" not in body
    assert "Chhattisgarh" not in body
    assert "91.3" not in body
    assert "27.1" in body or "11.2" in body
    assert not is_dash_soup(body)


def test_quote_facts_includes_outlook_days():
    q = quote_facts(
        {
            "forecast": {
                "label": "Malda, West Bengal",
                "temp_c": 27.1,
                "precip_next_3d_mm": 11.2,
                "precip_7d_mm": 22.0,
                "outlook_days": [
                    {"date": "2026-08-19", "precip_mm": 4.2, "precip_prob_pct": 70, "temp_max_c": 32.0}
                ],
            }
        }
    )
    assert "Malda" in q
    assert "4.2" in q
    assert "32" in q


def test_howrah_advisor_plan_does_not_rank_chhattisgarh():
    p = interpret("Flood risk in Howrah")
    assert p.mode == "data"
    assert "rank" not in p.needs or loc("Howrah").state in (p.states or [loc("Howrah").state])
    assert "Chhattisgarh" not in (p.states or [])

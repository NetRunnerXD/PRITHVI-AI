"""A bare Indian name is a forecast request. Hello is chat. Unknown is refuse."""

import json

import pytest

from app.agents.facts import looks_like_bare_place, source_gate
from app.agents.utterance import interpret
from app.schemas.chat import ChatRequest
from app.services.location_svc import resolve_location, resolve_named_place


def test_bare_puruliya_needs_forecast():
    assert looks_like_bare_place("Puruliya")
    g = source_gate("Puruliya")
    assert g.mode == "data"
    assert g.needs == ["forecast"]
    loc = resolve_named_place("Puruliya")
    assert loc and loc.district == "Purulia"
    assert loc.state == "West Bengal"


def test_contradiction_hello_is_not_a_place():
    assert not looks_like_bare_place("hello")
    assert not looks_like_bare_place("hello there")
    g = source_gate("hello there")
    assert g.mode == "chat"
    assert g.needs == []


def test_contradiction_noida_not_blocked_by_no():
    assert looks_like_bare_place("Noida")
    g = source_gate("Noida")
    assert g.mode == "data"
    assert resolve_named_place("Noida").place_name == "Noida"


def test_bare_puri_is_puri_not_purulia():
    g = source_gate("Puri")
    assert g.mode == "data"
    loc = resolve_named_place("Puri")
    assert loc.state == "Odisha"
    assert loc.district != "Purulia"


def test_bare_state_is_capital_forecast():
    g = source_gate("Odisha")
    assert g.mode == "data"
    assert "forecast" in g.needs
    loc = resolve_named_place("Odisha")
    assert loc is not None
    assert loc.place_name == "Bhubaneswar"
    assert loc.state == "Odisha"


def test_bare_atlantis_refuses():
    g = source_gate("Atlantis")
    assert g.mode == "refuse"
    assert g.needs == []


def test_contradiction_puruliya_weather_sentence_is_still_forecast():
    """Bare Puruliya fetches; so must the explicit weather sentence — never a chat shrug."""
    g = source_gate("How about the weather condition in Puruliya")
    assert g.mode == "data"
    assert "forecast" in g.needs
    chat = source_gate("How about a joke")
    assert chat.mode != "data" or "forecast" not in chat.needs


def test_what_about_kerala_is_not_bare():
    """Follow-up phrasing must stay a follow-up, not a bare-place forecast."""
    assert not looks_like_bare_place("what about Kerala?")
    g = source_gate("what about Kerala?")
    assert g.mode != "refuse"
    assert g.needs != ["forecast"]


@pytest.mark.asyncio
async def test_orchestrator_puruliya_fetches_forecast_not_haldia(monkeypatch):
    from app.agents import orchestrator
    from app.llm import ollama_client

    async def fake_ping():
        return True, "qwen2.5"

    async def fake_chat(messages, tools=None):
        return {
            "content": "Conditions look ordinary.",
            "tool_calls": [],
            "tools_stripped": False,
        }

    fetched = []

    async def fake_call(self, args):
        fetched.append((args.get("need"), getattr(self, "loc", None)))
        loc = self.loc
        return {
            "need": args.get("need"),
            "place": loc.place_name or loc.district,
            "label": loc.label,
            "temp_c": 31.4,
            "precip_next_3d_mm": 12.0,
            "precip_7d_mm": 20.0,
        }

    monkeypatch.setattr(ollama_client, "ping", fake_ping)
    monkeypatch.setattr(ollama_client, "chat", fake_chat)
    monkeypatch.setattr("app.agents.data_tool.DataLib.call", fake_call)

    pin = resolve_location(q="Haldia")
    events = []
    async for ev in orchestrator.run_agent(ChatRequest(message="Puruliya", location=pin)):
        events.append(ev)
    final = next(e for e in events if e["type"] == "final")["message"]
    assert fetched and fetched[0][0] == "forecast"
    loc = fetched[0][1]
    assert loc.district == "Purulia"
    assert loc.state == "West Bengal"
    body = final.get("content_en") or ""
    assert "31.4" in body or "12" in body
    assert "couldn't find" not in body.lower()
    assert "Puri," not in body
    assert "Haldia" not in body


@pytest.mark.asyncio
async def test_orchestrator_drops_couldnt_find_when_forecast_exists(monkeypatch):
    from app.agents import orchestrator
    from app.llm import ollama_client

    async def fake_ping():
        return True, "qwen2.5"

    async def fake_chat(messages, tools=None):
        return {
            "content": "I couldn't find any specific weather, AQI, or flood data for Puruliya.",
            "tool_calls": [],
            "tools_stripped": False,
        }

    async def fake_call(self, args):
        loc = self.loc
        return {
            "need": "forecast",
            "place": loc.place_name or loc.district,
            "label": loc.label,
            "temp_c": 25.2,
            "precip_next_3d_mm": 8.4,
            "precip_7d_mm": 29.6,
        }

    monkeypatch.setattr(ollama_client, "ping", fake_ping)
    monkeypatch.setattr(ollama_client, "chat", fake_chat)
    monkeypatch.setattr("app.agents.data_tool.DataLib.call", fake_call)

    events = []
    async for ev in orchestrator.run_agent(
        ChatRequest(message="Puruliya", location=resolve_location(q="Haldia"))
    ):
        events.append(ev)
    body = next(e for e in events if e["type"] == "final")["message"].get("content_en") or ""
    assert "couldn't find" not in body.lower()
    assert "25.2" in body
    assert "Purulia" in body
    assert "Haldia" not in body


@pytest.mark.asyncio
async def test_orchestrator_atlantis_does_not_fetch(monkeypatch):
    from app.agents import orchestrator
    from app.llm import ollama_client

    called = {"chat": 0, "data": 0}

    async def fake_ping():
        return True, "qwen2.5"

    async def fake_chat(messages, tools=None):
        called["chat"] += 1
        return {"content": "I will invent 88 mm for Atlantis.", "tool_calls": [], "tools_stripped": False}

    async def fake_call(self, args):
        called["data"] += 1
        return {"need": args.get("need"), "temp_c": 28}

    monkeypatch.setattr(ollama_client, "ping", fake_ping)
    monkeypatch.setattr(ollama_client, "chat", fake_chat)
    monkeypatch.setattr("app.agents.data_tool.DataLib.call", fake_call)

    pin = resolve_location(q="Haldia")
    events = []
    async for ev in orchestrator.run_agent(ChatRequest(message="Puruliya weather".replace("Puruliya", "Atlantis"), location=pin)):
        events.append(ev)
    # message is "Atlantis weather"
    final = next(e for e in events if e["type"] == "final")["message"]
    assert called["data"] == 0
    assert called["chat"] == 0
    body = final.get("content_en") or ""
    assert "88" not in body
    assert "Haldia" not in body
    assert "Atlantis" in body
    assert "Rituchakra" in body

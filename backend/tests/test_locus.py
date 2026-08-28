"""Dashboard pin is the weather locus unless the user named another Indian place."""

from __future__ import annotations

import json

import pytest

from app.schemas.chat import ChatRequest
from app.services.location_svc import resolve_location


def _loc(name: str):
    hit = resolve_location(q=name)
    assert hit is not None
    return hit


@pytest.mark.asyncio
async def test_llm_haldia_place_is_clamped_to_howrah_pin(monkeypatch):
    from app.agents import orchestrator
    from app.llm import ollama_client

    seen: list[str] = []
    round_id = {"n": 0}

    async def fake_ping():
        return True, "qwen2.5"

    async def fake_chat(messages, tools=None):
        round_id["n"] += 1
        if round_id["n"] == 1 and tools:
            return {
                "content": "",
                "tool_calls": [
                    {
                        "id": "c1",
                        "name": "data",
                        "arguments": json.dumps({"need": "forecast", "place": "Haldia"}),
                    }
                ],
                "tools_stripped": False,
            }
        return {"content": "Haldia will see 91.3 mm.", "tool_calls": [], "tools_stripped": False}

    async def fake_call(self, args):
        seen.append(str(args.get("place") or ""))
        locn = self.loc
        return {
            "need": args.get("need") or "forecast",
            "place": locn.place_name or locn.district,
            "label": locn.label,
            "temp_c": 29.4,
            "precip_next_3d_mm": 7.1,
            "precip_7d_mm": 15.0,
        }

    monkeypatch.setattr(ollama_client, "ping", fake_ping)
    monkeypatch.setattr(ollama_client, "chat", fake_chat)
    monkeypatch.setattr("app.agents.data_tool.DataLib.call", fake_call)

    events = []
    async for ev in orchestrator.run_agent(
        ChatRequest(message="What's the weather today?", location=_loc("Howrah"))
    ):
        events.append(ev)
    body = next(e for e in events if e["type"] == "final")["message"].get("content_en") or ""
    traces = next(e for e in events if e["type"] == "final")["message"].get("tool_trace") or []
    assert any("Howrah" in p or "howrah" in p.lower() for p in seen)
    assert not any(p.lower() == "haldia" for p in seen)
    assert any(t.get("clamped_from") == "Haldia" for t in traces)
    assert "Howrah" in body
    assert "Haldia" not in body
    assert "91.3" not in body


@pytest.mark.asyncio
async def test_pin_change_drops_prior_malda(monkeypatch):
    from app.agents import orchestrator
    from app.llm import ollama_client

    seen: list[str] = []

    async def fake_ping():
        return True, "qwen2.5"

    async def fake_chat(messages, tools=None):
        return {"content": "Here is the pack.", "tool_calls": [], "tools_stripped": False}

    async def fake_call(self, args):
        seen.append(str(args.get("place") or self.loc.place_name or ""))
        locn = self.loc
        return {
            "need": args.get("need") or "forecast",
            "place": locn.place_name or locn.district,
            "label": locn.label,
            "temp_c": 26.0,
            "precip_next_3d_mm": 4.0,
            "precip_7d_mm": 9.0,
        }

    monkeypatch.setattr(ollama_client, "ping", fake_ping)
    monkeypatch.setattr(ollama_client, "chat", fake_chat)
    monkeypatch.setattr("app.agents.data_tool.DataLib.call", fake_call)

    cid = "locus-pin-move"
    async for _ in orchestrator.run_agent(
        ChatRequest(message="How about malda", location=_loc("Haldia"), conversation_id=cid)
    ):
        pass
    seen.clear()
    events = []
    async for ev in orchestrator.run_agent(
        ChatRequest(message="What's the weather today?", location=_loc("Howrah"), conversation_id=cid)
    ):
        events.append(ev)
    body = next(e for e in events if e["type"] == "final")["message"].get("content_en") or ""
    assert any("Howrah" in p for p in seen)
    assert not any("Malda" in p or "Haldia" in p for p in seen)
    assert "Howrah" in body
    assert "Malda" not in body
    assert "Haldia" not in body


@pytest.mark.asyncio
async def test_same_pin_followup_keeps_malda(monkeypatch):
    from app.agents import orchestrator
    from app.llm import ollama_client

    seen: list[str] = []

    async def fake_ping():
        return True, "qwen2.5"

    async def fake_chat(messages, tools=None):
        return {"content": "Here is the pack.", "tool_calls": [], "tools_stripped": False}

    async def fake_call(self, args):
        seen.append(str(args.get("place") or self.loc.place_name or ""))
        locn = self.loc
        return {
            "need": args.get("need") or "aqi",
            "place": locn.place_name or locn.district,
            "label": locn.label,
            "om_us_aqi": 64,
            "provider_status": "missing",
            "temp_c": 26.0,
            "precip_next_3d_mm": 4.0,
            "precip_7d_mm": 9.0,
        }

    monkeypatch.setattr(ollama_client, "ping", fake_ping)
    monkeypatch.setattr(ollama_client, "chat", fake_chat)
    monkeypatch.setattr("app.agents.data_tool.DataLib.call", fake_call)

    cid = "locus-same-pin"
    async for _ in orchestrator.run_agent(
        ChatRequest(message="How about malda", location=_loc("Haldia"), conversation_id=cid)
    ):
        pass
    seen.clear()
    events = []
    async for ev in orchestrator.run_agent(
        ChatRequest(message="AQI?", location=_loc("Haldia"), conversation_id=cid)
    ):
        events.append(ev)
    body = next(e for e in events if e["type"] == "final")["message"].get("content_en") or ""
    assert any("Malda" in p for p in seen)
    assert "Malda" in body
    assert "Haldia" not in body

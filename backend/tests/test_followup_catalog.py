"""Follow-ups stay on the last town. 'all of them' is not a place. Catalog is the full pack."""

import pytest

from app.agents.data_tool import suggestions_for
from app.agents.utterance import (
    CATALOG_NEEDS,
    interpret,
    is_followup_affirm,
    looks_like_bare_place,
    wants_catalog,
)
from app.schemas.chat import ChatRequest
from app.services.location_svc import resolve_location, resolve_named_place


def test_all_of_them_is_not_a_place():
    assert not looks_like_bare_place("all of them")
    assert not looks_like_bare_place("yes")
    assert not looks_like_bare_place("the rest")
    assert is_followup_affirm("all of them")
    assert is_followup_affirm("yes")
    p = interpret("all of them")
    assert p.follow
    assert p.mode != "refuse"


def test_contradiction_puruliya_is_still_a_place():
    assert looks_like_bare_place("Puruliya")
    assert not is_followup_affirm("Puruliya")
    p = interpret("Puruliya")
    assert p.mode == "data"
    assert p.needs == ["forecast"]


def test_catalog_question_fetches_full_pack():
    assert wants_catalog("List all metrics present on Rituchakra for Puruliya")
    p = interpret("List all metrics present on Rituchakra for Puruliya")
    assert p.mode == "data"
    assert p.catalog
    for n in ("forecast", "nowcast", "aqi", "warnings", "risks", "mandi"):
        assert n in p.needs
    assert p.asked and "purul" in p.asked.lower()


def test_contradiction_single_aqi_is_not_catalog():
    p = interpret("AQI in Jaipur")
    assert p.needs == ["aqi"]
    assert not p.catalog


@pytest.mark.asyncio
async def test_chain_catalog_then_yes_then_all_of_them(monkeypatch):
    from app.agents import orchestrator
    from app.llm import ollama_client

    async def fake_ping():
        return True, "qwen2.5"

    async def fake_chat(messages, tools=None):
        return {"content": "Here is the Rituchakra pack.", "tool_calls": [], "tools_stripped": False}

    fetched: list[tuple[str, str]] = []

    async def fake_call(self, args):
        need = str(args.get("need") or "")
        loc = self.loc
        fetched.append((need, loc.place_name or loc.district))
        return {
            "need": need,
            "place": loc.place_name,
            "label": loc.label,
            "temp_c": 25.2,
            "precip_next_3d_mm": 8.4,
            "precip_7d_mm": 29.6,
            "nowcast": {"p_interrupt_90m": 0.2},
            "cpcb": {"value": 87, "category": "Moderate", "station": "Victoria"},
            "provider_status": "ok",
            "warnings": [{"title": "Watch"}],
            "risks": [{"id": "flood", "label": "Flood", "score_pct": 40, "severity": "medium"}],
            "mandi": [],
            "unavailable": {"radar": "No radar ingest."},
        }

    monkeypatch.setattr(ollama_client, "ping", fake_ping)
    monkeypatch.setattr(ollama_client, "chat", fake_chat)
    monkeypatch.setattr("app.agents.data_tool.DataLib.call", fake_call)

    pin = resolve_location(q="Haldia")
    cid = "catalog-chain"

    async def turn(q: str):
        events = []
        async for ev in orchestrator.run_agent(ChatRequest(message=q, location=pin, conversation_id=cid)):
            events.append(ev)
        return next(e for e in events if e["type"] == "final")["message"]

    first = await turn("List all metrics present on Rituchakra for Puruliya")
    needs1 = {n for n, _ in fetched}
    assert "forecast" in needs1
    assert "aqi" in needs1
    assert all(place != "Haldia" for _, place in fetched)
    assert "Purulia" in (first.get("content_en") or "") or "25.2" in (first.get("content_en") or "")
    sugg = first.get("suggestions") or []
    assert sugg
    assert all(s.get("location") for s in sugg)
    assert all("Haldia" not in (s.get("label") or "") for s in sugg)
    map_chip = next(s for s in sugg if s.get("tab") == "map")
    assert map_chip["location"]["district"] == "Purulia" or map_chip["location"]["place_name"] == "Purulia"
    assert map_chip["center"][0] != pin.lat

    fetched.clear()
    second = await turn("yes")
    body2 = (second.get("content_en") or "").lower()
    assert "gazetteer" not in body2
    assert "all of them" not in body2
    assert all(place != "Haldia" for _, place in fetched)

    fetched.clear()
    third = await turn("all of them")
    body3 = third.get("content_en") or ""
    assert "not a place" not in body3.lower()
    assert "gazetteer" not in body3.lower()
    assert "Haldia" not in body3
    assert all(place != "Haldia" for _, place in fetched)


@pytest.mark.asyncio
async def test_contradiction_all_of_them_first_turn_does_not_fetch_pin(monkeypatch):
    from app.agents import orchestrator
    from app.llm import ollama_client

    called = {"data": 0}

    async def fake_ping():
        return True, "qwen2.5"

    async def fake_chat(messages, tools=None):
        return {"content": "Which Indian town?", "tool_calls": [], "tools_stripped": False}

    async def fake_call(self, args):
        called["data"] += 1
        return {"need": args.get("need"), "temp_c": 20}

    monkeypatch.setattr(ollama_client, "ping", fake_ping)
    monkeypatch.setattr(ollama_client, "chat", fake_chat)
    monkeypatch.setattr("app.agents.data_tool.DataLib.call", fake_call)

    events = []
    async for ev in orchestrator.run_agent(
        ChatRequest(message="all of them", location=resolve_location(q="Haldia"))
    ):
        events.append(ev)
    final = next(e for e in events if e["type"] == "final")["message"]
    assert called["data"] == 0
    assert "gazetteer" not in (final.get("content_en") or "").lower()


def test_suggestions_carry_the_discussed_place():
    loc = resolve_named_place("Puruliya")
    assert loc
    chips = suggestions_for({"forecast": {"need": "forecast"}}, loc)
    assert chips
    for s in chips:
        assert s.get("location")
        assert s["location"]["district"] == "Purulia" or s["location"]["place_name"] == "Purulia"
        assert s.get("tab")
    assert any(s.get("tab") == "map" for s in chips)
    assert any(s.get("tab") == "forecast" for s in chips)

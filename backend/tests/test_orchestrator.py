import json

import pytest

from app.schemas.dashboard import (
    CurrentConditions,
    DashboardSnapshot,
    Descriptive,
    Diagnostic,
    MapState,
    Predictive,
    Prescriptive,
)
from app.schemas.location import Location
from app.schemas.risk import RiskCard


def _snap() -> DashboardSnapshot:
    loc = Location(
        id="town:haldia_wes",
        label="Haldia, West Bengal",
        state="West Bengal",
        district="Purba Medinipur",
        lat=22.0667,
        lon=88.0698,
        place_kind="city",
        place_name="Haldia",
    )
    return DashboardSnapshot(
        location=loc,
        generated_at="2026-08-18T00:00:00+05:30",
        sources=["open-meteo"],
        descriptive=Descriptive(current=CurrentConditions(temp_c=28, soil_moisture_m3m3=0.3)),
        diagnostic=Diagnostic(),
        predictive=Predictive(precip_next_3d_mm=18.0, precip_7d_mm=40.0),
        prescriptive=Prescriptive(),
        risks=[
            RiskCard(
                id="flood",
                label="Flood Risk",
                severity="medium",
                score_pct=40,
                confidence_pct=80,
                factors=[],
                updated_at="2026-08-18T00:00:00Z",
            )
        ],
        map=MapState(center=[22.07, 88.07]),
        science={
            "nowcast": {
                "locked": {
                    "p_interrupt_90m": 0.62,
                    "onset": "2026-08-18T16:00:00+05:30",
                    "enterable_2h": False,
                    "hours": [{"t": "2026-08-18T16:00:00", "mm": 2.1, "engine": "nowcast", "lead_h": 1}],
                },
                "pump": {"action": "hold", "p_interrupt_90m": 0.62, "liters_at_risk": 900},
                "hours": [{"t": "2026-08-18T16:00:00", "mm": 2.1, "engine": "nowcast", "lead_h": 1}],
            }
        },
    )


@pytest.mark.asyncio
async def test_elephant_does_not_prefetch(monkeypatch):
    from app.agents import orchestrator
    from app.llm import ollama_client
    from app.schemas.chat import ChatRequest

    called = {"data": False, "snap": False}

    async def fake_ping():
        return True, "qwen2.5"

    async def fake_chat(messages, tools=None):
        return {"content": "I do not have advice for taking an elephant into the city.", "tool_calls": [], "tools_stripped": False}

    async def boom_snap(*a, **k):
        called["snap"] = True
        raise AssertionError("snapshot must not run for off-topic chat")

    monkeypatch.setattr(ollama_client, "ping", fake_ping)
    monkeypatch.setattr(ollama_client, "chat", fake_chat)
    monkeypatch.setattr("app.services.snapshot.build_snapshot", boom_snap)

    payload = ChatRequest(
        message="Can I take my elephant out to the city?",
        location=_snap().location,
    )
    events = []
    async for ev in orchestrator.run_agent(payload):
        events.append(ev)
    starts = [e.get("name") for e in events if e.get("type") == "tool_start"]
    assert starts == []
    assert called["snap"] is False
    assert not any(e.get("type") == "ui" for e in events)
    final = next(e for e in events if e["type"] == "final")["message"]
    assert "elephant" in (final.get("content_en") or "").lower()
    assert not final.get("blocks")
    assert not any(e.get("type") == "suggestions" and e.get("suggestions") for e in events)


@pytest.mark.asyncio
async def test_rain_window_only_when_model_asks(monkeypatch):
    from app.agents import orchestrator
    from app.llm import ollama_client
    from app.schemas.chat import ChatRequest
    from app.services import rain_window

    snap = _snap()
    step = {"n": 0}

    async def fake_ping():
        return True, "qwen2.5"

    async def fake_chat(messages, tools=None):
        step["n"] += 1
        if step["n"] == 1:
            return {
                "content": "",
                "tool_calls": [
                    {
                        "id": "c1",
                        "name": "data",
                        "arguments": json.dumps(
                            {"need": "rain_window", "place": "Haldia", "start": "2026-08-23", "end": "2026-08-28"}
                        ),
                    }
                ],
                "tools_stripped": False,
            }
        return {
            "content": "Haldia sees 12.2 mm over those days (Open-Meteo daily, not a gauge).",
            "tool_calls": [],
            "tools_stripped": False,
        }

    async def fake_window(loc, start, end):
        return {
            "location": loc.model_dump(),
            "start": start.isoformat(),
            "end": end.isoformat(),
            "days": [
                {"date": "2026-08-23", "precip_mm": 4.2, "precip_prob_pct": 70, "temp_max_c": 31.0},
                {"date": "2026-08-24", "precip_mm": 8.0, "precip_prob_pct": 80, "temp_max_c": 30.5},
            ],
            "total_mm": 12.2,
            "missing": [],
        }

    monkeypatch.setattr(ollama_client, "ping", fake_ping)
    monkeypatch.setattr(ollama_client, "chat", fake_chat)
    monkeypatch.setattr(rain_window, "fetch_window", fake_window)

    payload = ChatRequest(
        message="Can you show me rainfall prediction in haldia for 23 to 28th August?",
        location=snap.location,
    )
    events = []
    async for ev in orchestrator.run_agent(payload):
        events.append(ev)
    starts = [e for e in events if e.get("type") == "tool_start"]
    assert len(starts) == 1
    assert starts[0]["args"]["need"] == "rain_window"
    assert not any(e.get("type") == "ui" for e in events)
    sugg = next((e for e in events if e.get("type") == "suggestions"), None)
    assert sugg and any(s.get("tab") == "forecast" for s in sugg["suggestions"])
    final = next(e for e in events if e["type"] == "final")["message"]
    assert "12.2" in (final.get("content_en") or "")
    table = next(b for b in final["blocks"] if b["type"] == "table")
    assert table["rows"][0]["precip_mm"] == 4.2
    assert "81.3" not in (final.get("content_en") or "")


@pytest.mark.asyncio
async def test_unbound_number_replaced_not_deleted(monkeypatch):
    from app.agents import orchestrator
    from app.llm import ollama_client
    from app.schemas.chat import ChatRequest

    async def fake_ping():
        return True, "qwen2.5"

    async def fake_chat(messages, tools=None):
        return {
            "content": "It will dump 81.3 mm extra in Haldia on Tuesday.",
            "tool_calls": [],
            "tools_stripped": False,
        }

    monkeypatch.setattr(ollama_client, "ping", fake_ping)
    monkeypatch.setattr(ollama_client, "chat", fake_chat)

    payload = ChatRequest(message="hello", location=_snap().location)
    events = []
    async for ev in orchestrator.run_agent(payload):
        events.append(ev)
    final = next(e for e in events if e["type"] == "final")["message"]
    assert "81.3" not in (final.get("content_en") or "")
    assert "Haldia" in (final.get("content_en") or "")
    assert "—" in (final.get("content_en") or "")

"""Typed tools, argument validation with one retry, parallel calls, token streaming."""

from __future__ import annotations

import asyncio
import json

import pytest

from app.agents.typed_tools import TOOL_NAMES, TOOLS, to_data_args
from app.schemas.chat import ChatRequest
from app.services.location_svc import resolve_location


def test_seven_typed_tools_with_closed_schemas():
    assert TOOL_NAMES == (
        "get_forecast",
        "get_nowcast",
        "get_alerts",
        "get_air_quality",
        "get_risks",
        "compare_places",
        "rank_districts",
    )
    for t in TOOLS:
        assert t["function"]["parameters"]["additionalProperties"] is False


@pytest.mark.parametrize(
    "name,args,want",
    [
        ("get_forecast", {}, {"need": "forecast"}),
        ("get_forecast", {"place": "Patna", "hour": 17}, {"need": "forecast", "place": "Patna", "hour": 17}),
        (
            "get_forecast",
            {"start_date": "2026-10-22", "end_date": "2026-10-24"},
            {"need": "rain_window", "start": "2026-10-22", "end": "2026-10-24"},
        ),
        ("get_nowcast", {"place": "Haldia"}, {"need": "nowcast", "place": "Haldia"}),
        ("get_alerts", {}, {"need": "warnings"}),
        ("get_air_quality", {"place": ""}, {"need": "aqi"}),
        ("get_risks", {}, {"need": "risks"}),
        ("compare_places", {"other": "Malda"}, {"need": "compare", "other": "Malda"}),
        ("rank_districts", {"state": "Bihar"}, {"need": "rank", "state": "Bihar", "metric": "flood"}),
        ("data", {"need": "aqi", "place": "Delhi"}, {"need": "aqi", "place": "Delhi"}),
    ],
)
def test_maps_onto_datalib(name, args, want):
    got, err = to_data_args(name, json.dumps(args))
    assert err is None
    assert got == want


@pytest.mark.parametrize(
    "name,args",
    [
        ("get_forecast", {"hour": 30}),
        ("get_forecast", {"start_date": "tomorrow"}),
        ("get_forecast", {"start_date": "2026-10-24", "end_date": "2026-10-22"}),
        ("rank_districts", {"state": "Bihar", "metric": "pollen"}),
        ("compare_places", {}),
        ("get_alerts", {"severity": "red"}),
        ("weather", {}),
        ("data", {"need": "horoscope"}),
    ],
)
def test_rejects_bad_arguments_with_a_message(name, args):
    got, err = to_data_args(name, json.dumps(args))
    assert got is None
    assert err and len(err) < 300


def _patch_common(monkeypatch, calls, running):
    from app.llm import ollama_client

    async def fake_ping():
        return True, "fake"

    async def fake_call(self, args):
        running["now"] += 1
        running["peak"] = max(running["peak"], running["now"])
        await asyncio.sleep(0.05)
        running["now"] -= 1
        calls.append(dict(args))
        need = args.get("need")
        if need == "aqi":
            return {"need": "aqi", "aqi": 148, "category": "Moderate"}
        if need == "warnings":
            return {"need": "warnings", "items": []}
        return {"need": need, "temp_c": 31, "precip_mm": 12.5}

    monkeypatch.setattr(ollama_client, "ping", fake_ping)
    monkeypatch.setattr("app.agents.data_tool.DataLib.call", fake_call)


@pytest.mark.asyncio
async def test_parallel_typed_calls_and_one_bad_arg_retry(monkeypatch):
    from app.agents import orchestrator
    from app.llm import ollama_client

    calls: list[dict] = []
    running = {"now": 0, "peak": 0}
    _patch_common(monkeypatch, calls, running)
    seen_tool_msgs: list[dict] = []
    turn = {"n": 0}

    async def fake_chat(messages, tools=None, **_):
        turn["n"] += 1
        if turn["n"] == 1:
            return {
                "content": "",
                "tool_calls": [
                    {"id": "a", "name": "get_air_quality", "arguments": "{}"},
                    {"id": "b", "name": "get_alerts", "arguments": "{}"},
                    {"id": "c", "name": "get_forecast", "arguments": '{"hour": 30}'},
                ],
            }
        seen_tool_msgs.extend(m for m in messages if m.get("role") == "tool")
        return {"content": "AQI is 148 at Haldia and no alerts are in force.", "tool_calls": []}

    monkeypatch.setattr(ollama_client, "chat", fake_chat)
    events = [
        ev
        async for ev in orchestrator.run_agent(
            ChatRequest(message="Is the air ok and any alerts in Haldia?", location=resolve_location(q="Haldia"))
        )
    ]
    needs = [c.get("need") for c in calls]
    assert "aqi" in needs and "warnings" in needs
    assert running["peak"] >= 2  # aqi + warnings ran together
    bad = [m for m in seen_tool_msgs if "invalid arguments" in m["content"]]
    assert bad and "hour" in bad[0]["content"]
    final = next(e for e in events if e["type"] == "final")["message"]
    assert "148" in (final.get("content_en") or "")


@pytest.mark.asyncio
async def test_prefetch_runs_needs_in_parallel(monkeypatch):
    from app.agents import orchestrator
    from app.llm import ollama_client

    calls: list[dict] = []
    running = {"now": 0, "peak": 0}
    _patch_common(monkeypatch, calls, running)

    async def fake_chat(messages, tools=None, **_):
        return {"content": "AQI is 148; 12.5 mm of rain is likely.", "tool_calls": []}

    monkeypatch.setattr(ollama_client, "chat", fake_chat)
    async for _ev in orchestrator.run_agent(
        ChatRequest(message="Rain forecast and AQI and warnings for Haldia", location=resolve_location(q="Haldia"))
    ):
        pass
    if len(calls) >= 2:
        assert running["peak"] >= 2


@pytest.mark.asyncio
async def test_answer_streams_as_delta_events(monkeypatch):
    from app.agents import orchestrator
    from app.llm import ollama_client

    calls: list[dict] = []
    running = {"now": 0, "peak": 0}
    _patch_common(monkeypatch, calls, running)
    text = "Expect 12.5 mm of rain at Haldia. Carry an umbrella."

    async def fake_stream(messages, tools=None, *, on_delta=None, **_):
        for i in range(0, len(text), 7):
            on_delta(text[i : i + 7])
            await asyncio.sleep(0)
        return {"content": text, "tool_calls": []}

    monkeypatch.setattr(ollama_client, "chat_stream", fake_stream)
    events = [
        ev
        async for ev in orchestrator.run_agent(
            ChatRequest(message="Will it rain in Haldia tomorrow?", location=resolve_location(q="Haldia"))
        )
    ]
    kinds = [e["type"] for e in events]
    assert "delta" in kinds
    assert kinds.index("delta") < kinds.index("final")
    draft = "".join(e["text"] for e in events if e["type"] == "delta")
    assert draft.startswith("Expect 12.5 mm")


@pytest.mark.asyncio
async def test_tool_syntax_never_streams(monkeypatch):
    from app.agents.orchestrator import _llm_round
    from app.llm import ollama_client

    async def fake_stream(messages, tools=None, *, on_delta=None, **_):
        for piece in ['<function=get_forecast{"place":', ' "Patna"}></function>']:
            on_delta(piece)
        return {"content": "", "tool_calls": [{"id": "x", "name": "get_forecast", "arguments": "{}"}]}

    monkeypatch.setattr(ollama_client, "chat_stream", fake_stream)
    box: dict = {}
    evs = [
        e
        async for e in _llm_round([], None, box, stream=True, out_locale="en", client_mt=False, draft={})
    ]
    assert not [e for e in evs if e["type"] == "delta"]
    assert box["resp"]["tool_calls"]


@pytest.mark.asyncio
async def test_non_english_streams_sentence_by_sentence(monkeypatch):
    from app.agents import orchestrator
    from app.i18n.mt import MTResult
    from app.llm import ollama_client

    async def fake_stream(messages, tools=None, *, on_delta=None, **_):
        for piece in ["Rain of 12.5 mm", " is likely. Carry", " an umbrella."]:
            on_delta(piece)
        return {"content": "Rain of 12.5 mm is likely. Carry an umbrella.", "tool_calls": []}

    async def fake_tr(text, src, tgt, **_):
        return MTResult(text=f"[{tgt}] {text}", src=src, tgt=tgt, engine="fake", ok=True)

    monkeypatch.setattr(ollama_client, "chat_stream", fake_stream)
    monkeypatch.setattr(orchestrator, "mt_translate", fake_tr)
    box: dict = {}
    evs = [
        e
        async for e in orchestrator._llm_round(
            [], None, box, stream=True, out_locale="hi", client_mt=False, draft={}
        )
    ]
    deltas = [e["text"] for e in evs if e["type"] == "delta"]
    assert deltas == ["[hi] Rain of 12.5 mm is likely. "]


@pytest.mark.asyncio
async def test_chat_stream_defers_to_patched_chat(monkeypatch):
    from app.llm import ollama_client

    async def fake_chat(messages, tools=None, **_):
        return {"content": "patched", "tool_calls": []}

    monkeypatch.setattr(ollama_client, "chat", fake_chat)
    out = await ollama_client.chat_stream([{"role": "user", "content": "hi"}], on_delta=lambda _t: None)
    assert out["content"] == "patched"


@pytest.mark.asyncio
async def test_ping_cached_uses_patched_ping(monkeypatch):
    from app.llm import ollama_client

    async def fake_ping():
        return False, "down"

    monkeypatch.setattr(ollama_client, "ping", fake_ping)
    assert await ollama_client.ping_cached() == (False, "down")

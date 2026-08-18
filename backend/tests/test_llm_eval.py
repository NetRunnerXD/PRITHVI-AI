"""Rigorous chat eval: forgetful LLM vs independently known metrics."""

from __future__ import annotations

import json

import pytest

from app.agents.data_tool import DataLib
from app.schemas.chat import ChatRequest
from app.schemas.location import Location
from app.services.location_svc import resolve_location
from app.agents.eval_llm import load_cases, score_case

GOLD = {
    "rain_window": {
        "need": "rain_window",
        "location": {"place_name": "Haldia", "district": "Purba Medinipur", "label": "Haldia, West Bengal"},
        "start": "2026-08-23",
        "end": "2026-08-28",
        "total_mm": 12.2,
        "days": [
            {"date": "2026-08-23", "precip_mm": 4.2, "precip_prob_pct": 70},
            {"date": "2026-08-24", "precip_mm": 8.0, "precip_prob_pct": 80},
        ],
        "missing": [],
    },
    "nowcast": {
        "need": "nowcast",
        "nowcast": {"p_interrupt_90m": 0.62, "onset": "2026-08-18T16:00:00+05:30", "enterable_2h": False},
        "pump": {"action": "hold", "p_interrupt_90m": 0.62},
        "place": "Haldia",
    },
    "forecast": {
        "need": "forecast",
        "place": "Haldia",
        "precip_next_3d_mm": 18.0,
        "precip_7d_mm": 40.0,
        "water_balance_7d_mm": 12.0,
        "outlook_days": [],
    },
    "aqi": {
        "need": "aqi",
        "cpcb": {"value": 87, "category": "Moderate", "station": "Victoria", "city": "Kolkata", "is_local_station": False},
        "place": "Haldia",
    },
    "mandi": {
        "need": "mandi",
        "mandi": [{"commodity": "Rice", "modal_price": 4900, "market": "Tamluk"}],
    },
    "warnings": {"need": "warnings", "warnings": [{"title": "Orange", "hazard": "weather", "severity": "severe"}]},
    "compare": {
        "need": "compare",
        "delta_a_minus_b": {"rain_3d_mm": 6.5, "flood_score": 4},
        "a": {"district": "Haldia"},
        "b": {"district": "Digha"},
    },
    "rank": {
        "need": "rank",
        "state": "West Bengal",
        "metric": "flood",
        "ranked": [{"district": "Nadia", "flood_score": 72, "precip_3d_mm": 55.0}],
    },
    "states_weather": {
        "need": "states_weather",
        "metric": "flood",
        "note": "weather/flood, not tourism",
        "ranked": [
            {"state": "Odisha", "district": "Khordha", "flood_score": 61, "precip_3d_mm": 22.0, "temp_max_c": 33.1},
            {"state": "West Bengal", "district": "Nadia", "flood_score": 58, "precip_3d_mm": 19.0, "temp_max_c": 32.0},
        ],
    },
    "risks": {
        "need": "risks",
        "risks": [{"id": "flood", "label": "Flood Risk", "score_pct": 54, "severity": "medium"}],
    },
    "capability": {
        "need": "capability",
        "available": False,
        "metric": "insat",
        "reason": "MOSDAC / INSAT is not wired. Kalman scenes are Open-Meteo model-analysis, not satellite.",
    },
}


def _loc(place: str) -> Location:
    return resolve_location(q=place)


@pytest.fixture
def forgetful_llm(monkeypatch):
    from app.llm import ollama_client

    async def fake_ping():
        return True, "qwen2.5"

    async def fake_chat(messages, tools=None):
        return {
            "content": "Conditions look unsettled. Stay aware and check official guidance.",
            "tool_calls": [],
            "tools_stripped": False,
        }

    monkeypatch.setattr(ollama_client, "ping", fake_ping)
    monkeypatch.setattr(ollama_client, "chat", fake_chat)


@pytest.fixture
def gold_data(monkeypatch):
    fetched: list[str] = []

    async def fake_call(self, args):
        need = str(args.get("need") or "")
        fetched.append(need)
        pack = dict(GOLD.get(need) or {"need": need, "error": "no-gold"})
        loc = getattr(self, "loc", None)
        if loc is not None:
            pack = dict(pack)
            if need == "rain_window":
                pack["location"] = {
                    "place_name": loc.place_name,
                    "district": loc.district,
                    "label": loc.label,
                }
            if need in {"forecast", "aqi", "nowcast"}:
                pack["place"] = loc.place_name or loc.district
                pack["label"] = loc.label
        return pack

    monkeypatch.setattr(DataLib, "call", fake_call)
    return fetched


@pytest.mark.asyncio
async def test_bulk_forgetful_llm_quotes_gold_metrics(forgetful_llm, gold_data):
    from app.agents.orchestrator import run_agent

    failures = []
    for case in load_cases():
        gold_data.clear()
        payload = ChatRequest(message=case["q"], location=_loc(case.get("place") or "Haldia"))
        final = None
        async for ev in run_agent(payload):
            if ev.get("type") == "final":
                final = ev["message"]
        assert final
        gold = {n: GOLD[n] for n in (case.get("needs") or []) if n in GOLD}
        row = score_case(case, final, gold, list(gold_data))
        if not row["ok"]:
            failures.append(row)
    assert not failures, json.dumps(failures, indent=2)


@pytest.mark.asyncio
async def test_offtopic_never_hits_weather_data(forgetful_llm, gold_data):
    from app.agents.orchestrator import run_agent

    for case in load_cases():
        if case.get("weather"):
            continue
        gold_data.clear()
        payload = ChatRequest(message=case["q"], location=_loc(case.get("place") or "Haldia"))
        final = None
        async for ev in run_agent(payload):
            if ev.get("type") == "final":
                final = ev["message"]
        weather_fetch = [n for n in gold_data if n in GOLD and n != "capability"]
        assert weather_fetch == [], (case["id"], gold_data)
        assert "12.2" not in ((final or {}).get("content_en") or "")
        assert "0.62" not in ((final or {}).get("content_en") or "")
        if case.get("refuse"):
            assert "Rituchakra" in ((final or {}).get("content_en") or "")


@pytest.mark.asyncio
async def test_conversation_chain_and_suggestions(forgetful_llm, gold_data):
    """Follow-up chain: rank → other state → refuse pet → sourced visit compare."""
    from app.agents.orchestrator import run_agent

    cid = "chain-eval-1"
    turns = [
        ("Flood ranking of Odisha", True, ["rank"]),
        ("what about Kerala?", True, ["rank"]),
        ("Best places to take my pet to visit", False, []),
        ("Should I visit Odisha or West Bengal", True, ["states_weather"]),
        ("AQI in Jaipur", True, ["aqi"]),
    ]
    for q, weather, expect in turns:
        gold_data.clear()
        payload = ChatRequest(message=q, location=_loc("Haldia"), conversation_id=cid)
        final = None
        async for ev in run_agent(payload):
            if ev.get("type") == "final":
                final = ev["message"]
        assert final
        if not weather:
            assert gold_data == []
            assert "pet" in (final.get("content_en") or "").lower() or "Rituchakra" in (final.get("content_en") or "")
            continue
        for n in expect:
            assert n in gold_data or any(str(x).startswith(n) for x in gold_data), (q, gold_data)
        text = final.get("content_en") or ""
        if "rank" in expect:
            assert "flood" in text.lower() or "61" in text or "score" in text.lower()
        if "states_weather" in expect:
            assert "Odisha" in text or "22" in text
        if "aqi" in expect:
            assert "87" in text
            assert "AQI 0" not in text


@pytest.mark.asyncio
async def test_sticky_refuse_on_still_tell_me(forgetful_llm, gold_data):
    from app.agents.orchestrator import run_agent

    cid = "refuse-chain"
    first = None
    async for ev in run_agent(ChatRequest(message="Should I take my elephant to the islands?", location=_loc("Haldia"), conversation_id=cid)):
        if ev.get("type") == "final":
            first = ev["message"]
    assert first and "elephant" in (first.get("content_en") or "").lower()
    gold_data.clear()
    second = None
    async for ev in run_agent(ChatRequest(message="Still tell me", location=_loc("Haldia"), conversation_id=cid)):
        if ev.get("type") == "final":
            second = ev["message"]
    assert second
    assert gold_data == []
    body = second.get("content_en") or ""
    assert "Haldia" not in body
    assert "WBPCB" not in body
    assert "pleasant trip" not in body.lower()
    assert "elephant" in body.lower() or "Rituchakra" in body

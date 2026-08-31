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


@pytest.mark.asyncio
async def test_howrah_pin_weather_does_not_quote_haldia(monkeypatch):
    from app.agents import orchestrator
    from app.llm import ollama_client

    async def fake_ping():
        return True, "qwen2.5"

    async def fake_chat(messages, tools=None):
        return {
            "content": "Haldia looks wet today with 91.3 mm.",
            "tool_calls": [],
            "tools_stripped": False,
        }

    async def fake_call(self, args):
        locn = self.loc
        return {
            "need": args.get("need") or "forecast",
            "place": locn.place_name or locn.district,
            "label": locn.label,
            "temp_c": 29.4,
            "precip_1h_mm": 0.2,
            "precip_next_3d_mm": 7.1,
            "precip_7d_mm": 15.0,
            "sky_label": "Cloudy",
        }

    monkeypatch.setattr(ollama_client, "ping", fake_ping)
    monkeypatch.setattr(ollama_client, "chat", fake_chat)
    monkeypatch.setattr("app.agents.data_tool.DataLib.call", fake_call)

    events = []
    async for ev in orchestrator.run_agent(
        ChatRequest(message="What's the weather today?", location=loc("Howrah"))
    ):
        events.append(ev)
    body = next(e for e in events if e["type"] == "final")["message"].get("content_en") or ""
    meta = next(e for e in events if e["type"] == "meta")
    assert "Howrah" in (meta["location"].get("label") or "")
    assert "Howrah" in body
    assert "Haldia" not in body
    assert "Malda" not in body
    assert "91.3" not in body


@pytest.mark.asyncio
async def test_hindi_reply_keeps_figures_when_mt_dashes(monkeypatch):
    from app.agents import orchestrator
    from app.i18n.mt import MTResult
    from app.llm import ollama_client

    async def fake_ping():
        return True, "qwen2.5"

    async def fake_chat(messages, tools=None):
        return {
            "content": "Howrah is 29.4°C with 7.1 mm in 3 days.",
            "tool_calls": [],
            "tools_stripped": False,
        }

    async def fake_call(self, args):
        locn = self.loc
        return {
            "need": "forecast",
            "place": locn.place_name or locn.district,
            "label": locn.label,
            "temp_c": 29.4,
            "precip_next_3d_mm": 7.1,
            "precip_7d_mm": 15.0,
        }

    async def dash_mt(text, tgt, src="en"):
        return MTResult(
            text="कितना — मिमी। तापमान —°C। अगले — दिन।",
            src="en",
            tgt="hi",
            engine="google-gtx",
            ok=True,
        )

    monkeypatch.setattr(ollama_client, "ping", fake_ping)
    monkeypatch.setattr(ollama_client, "chat", fake_chat)
    monkeypatch.setattr("app.agents.data_tool.DataLib.call", fake_call)
    monkeypatch.setattr(orchestrator, "mt_outbound", dash_mt)

    events = []
    async for ev in orchestrator.run_agent(
        ChatRequest(message="What's the weather today?", location=loc("Howrah"), output_locale="hi")
    ):
        events.append(ev)
    msg = next(e for e in events if e["type"] == "final")["message"]
    body = msg.get("content") or ""
    assert "29.4" in body
    assert "7.1" in body
    assert body.count("—") < 4
    from app.agents.facts import has_null_metrics

    assert not has_null_metrics(body)


@pytest.mark.asyncio
async def test_reply_in_buttons_force_locale(monkeypatch):
    from app.agents import orchestrator
    from app.i18n.detect import has_script
    from app.i18n.mt import MTResult
    from app.llm import ollama_client

    async def fake_ping():
        return True, "qwen2.5"

    async def fake_chat(messages, tools=None):
        return {"content": "Howrah: 29.4°C, 7.1 mm in 3 days.", "tool_calls": [], "tools_stripped": False}

    async def fake_call(self, args):
        return {
            "need": "forecast",
            "place": "Howrah",
            "label": "Howrah, West Bengal",
            "temp_c": 29.4,
            "precip_next_3d_mm": 7.1,
        }

    async def fake_in(text, hint=None):
        src = "hi" if any("\u0900" <= ch <= "\u097F" for ch in text or "") else "en"
        en = "How much rain in Howrah?" if src == "hi" else text
        return MTResult(text=en, src=src, tgt="en", engine="google-gtx", ok=True)

    async def fake_out(text, tgt, src="en"):
        if tgt == "hi":
            return MTResult(text="हावड़ा: 29.4°C, 3 दिन में 7.1 मिमी।", src="en", tgt="hi", engine="google-gtx", ok=True)
        if tgt == "bn":
            return MTResult(text="হাওড়া: 29.4°C, 3 দিনে 7.1 মিমি।", src="en", tgt="bn", engine="google-gtx", ok=True)
        return MTResult(text=text, src="en", tgt=tgt, engine="identity", ok=True)

    monkeypatch.setattr(ollama_client, "ping", fake_ping)
    monkeypatch.setattr(ollama_client, "chat", fake_chat)
    monkeypatch.setattr("app.agents.data_tool.DataLib.call", fake_call)
    monkeypatch.setattr(orchestrator, "mt_inbound", fake_in)
    monkeypatch.setattr(orchestrator, "mt_outbound", fake_out)

    hindi_q = "हावड़ा में कितनी बारिश?"
    locn = loc("Howrah")

    async def final_for(**kw):
        events = []
        async for ev in orchestrator.run_agent(ChatRequest(message=hindi_q, location=locn, locale_hint="en", **kw)):
            events.append(ev)
        return next(e for e in events if e["type"] == "final")["message"]

    forced_en = await final_for(output_locale="en")
    assert forced_en["locale"] == "en"
    assert forced_en["content"] == forced_en["content_en"]
    assert "29.4" in forced_en["content"]
    assert not has_script(forced_en["content"], "hi")

    forced_hi = await final_for(output_locale="hi")
    assert forced_hi["locale"] == "hi"
    assert has_script(forced_hi["content"], "hi")
    assert "29.4" in forced_hi["content"]
    assert "7.1" in forced_hi["content"]

    auto = await final_for(output_locale="auto")
    assert auto["locale"] == "hi"
    assert has_script(auto["content"], "hi")

    forced_bn = await final_for(output_locale="bn")
    assert forced_bn["locale"] == "bn"
    assert has_script(forced_bn["content"], "bn")
    assert "7.1" in forced_bn["content"]


@pytest.mark.asyncio
async def test_no_place_in_bengali_stays_on_gps_focus(monkeypatch):
    """Unnamed Indic question must use the dashboard/GPS pin, not a translated Patna."""
    from app.agents import orchestrator
    from app.i18n.mt import MTResult
    from app.llm import ollama_client

    async def fake_ping():
        return True, "qwen2.5"

    async def fake_in(text, hint=None):
        return MTResult(
            text="How much rain in the next 3 days in Patna, Bihar?",
            src="bn",
            tgt="en",
            engine="google-gtx",
            ok=True,
        )

    async def fake_chat(messages, tools=None):
        blob = " ".join(m.get("content") or "" for m in messages)
        assert "Patna" not in blob or "Howrah" in blob
        return {
            "content": "Howrah will see 12.4 mm over the next 3 days.",
            "tool_calls": [],
            "tools_stripped": False,
        }

    async def fake_call(self, args):
        assert "Patna" not in str(args.get("place") or "")
        locn = self.loc
        return {
            "need": "forecast",
            "place": locn.place_name or locn.district,
            "label": locn.label,
            "temp_c": 26.4,
            "precip_next_3d_mm": 12.4,
        }

    async def fake_out(text, tgt, src="en"):
        return MTResult(text=text, src="en", tgt=tgt, engine="identity", ok=True)

    monkeypatch.setattr(ollama_client, "ping", fake_ping)
    monkeypatch.setattr(ollama_client, "chat", fake_chat)
    monkeypatch.setattr("app.agents.data_tool.DataLib.call", fake_call)
    monkeypatch.setattr(orchestrator, "mt_inbound", fake_in)
    monkeypatch.setattr(orchestrator, "mt_outbound", fake_out)

    events = []
    async for ev in orchestrator.run_agent(
        ChatRequest(
            message="আগামী ৩ দিনে কত বৃষ্টি?",
            location=loc("Howrah"),
            output_locale="bn",
            locale_hint="bn",
        )
    ):
        events.append(ev)
    meta = next(e for e in events if e["type"] == "meta")
    msg = next(e for e in events if e["type"] == "final")["message"]
    assert "Howrah" in (meta["location"].get("label") or "")
    assert "Patna" not in (meta["location"].get("label") or "")
    body = (msg.get("content_en") or "") + " " + (msg.get("content") or "")
    assert "Patna" not in body
    assert "Bihar" not in body
    assert "12.4" in body or "Howrah" in body

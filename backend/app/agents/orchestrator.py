from __future__ import annotations

import json
import time
import uuid
from collections.abc import AsyncIterator
from typing import Any

from app.agents.intent_router import classify, extract_metric, extract_state, mentioned_place, required_tools
from app.agents.prompts import SYSTEM
from app.i18n.detect import detect_lang, pick_output_locale
from app.science.vernacular import observe_speech
from app.i18n.mt import inbound as mt_inbound, outbound as mt_outbound
from app.i18n.number_lock import lock_and_note
from app.i18n.translate_reply import compose_indic
from app.llm import ollama_client
from app.schemas.chat import ChatRequest
from app.schemas.location import Location
from app.services.location_svc import resolve_location
from app.services.snapshot import build_snapshot, primary_reply, snapshot_tool_views
from app.tools import build_registry


def _parse_args(raw: Any) -> dict[str, Any]:
    if isinstance(raw, dict):
        return raw
    if not raw:
        return {}
    try:
        data = json.loads(raw)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _compact_tools(collected: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    if "rank_districts" in collected:
        src = collected["rank_districts"] or {}
        out["rank_districts"] = {
            "state": src.get("state"),
            "metric": src.get("metric"),
            "method": src.get("method"),
            "count": src.get("count"),
            "ranked": [
                {
                    "district": r.get("district"),
                    "flood_score": r.get("flood_score"),
                    "precip_3d_mm": r.get("precip_3d_mm"),
                    "drought_score": r.get("drought_score"),
                    "soil_m3m3": r.get("soil_m3m3"),
                    "temp_max_c": r.get("temp_max_c"),
                }
                for r in (src.get("ranked") or [])[:20]
            ],
        }
    if "list_districts" in collected:
        src = collected["list_districts"] or {}
        out["list_districts"] = {
            "state": src.get("state"),
            "count": src.get("count"),
            "names": [d.get("district") for d in (src.get("districts") or [])],
        }
    if "get_state_mandi" in collected:
        src = collected["get_state_mandi"] or {}
        districts = src.get("districts") or {}
        out["get_state_mandi"] = {
            "state": src.get("state"),
            "status": src.get("status"),
            "districts": {k: v[:4] for k, v in list(districts.items())[:25]},
        }
    for k, v in collected.items():
        if k not in out:
            out[k] = v
    return out


def _ensure_ranking(text: str, collected: dict[str, Any]) -> str:
    src = (collected.get("rank_districts") or {}) if collected else {}
    ranked = src.get("ranked") or []
    if not ranked:
        return text
    top = ranked[0].get("district") or ""
    if top and text and top.lower() in text.lower():
        return text
    lines = [
        f"{i+1}. {r.get('district')} — flood {r.get('flood_score')}, rain {r.get('precip_3d_mm')} mm / 3d"
        for i, r in enumerate(ranked[:12])
    ]
    header = f"Live {src.get('metric', 'flood')} ranking for {src.get('state')} ({src.get('method')}):\n" + "\n".join(lines)
    return f"{header}\n\n{text}".strip()


def _tool_args(name: str, loc: Location, state: str | None, metric: str, message: str) -> dict[str, Any]:
    if name in {"list_districts", "rank_districts", "get_state_mandi"}:
        args: dict[str, Any] = {"state": state or loc.state}
        if name == "rank_districts":
            args["metric"] = metric
            args["limit"] = 30
        return args
    if name == "compare_districts":
        other = None
        low = message.lower()
        for token in (" vs ", " versus ", " with ", " and "):
            if token in low:
                other = message[low.index(token) + len(token) :].strip(" ?.")
                break
        return {"other": other or "Pune"}
    if name == "predict_district":
        return {"name": loc.district}
    if name == "get_air_quality":
        return {"place": loc.district}
    if name == "get_nowcast":
        return {"speech": message}
    if name in {"get_weather_forecast", "get_soil_moisture", "get_prescriptions"}:
        return {}
    return {}


async def _english_history(history: list[Any] | None) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    for h in (history or [])[-6]:
        role = h.role if getattr(h, "role", None) in {"user", "assistant"} else "user"
        ready = getattr(h, "content_en", None)
        raw = getattr(h, "content", None) or ""
        if ready:
            content = ready
        else:
            pack = await mt_inbound(raw, getattr(h, "locale", None))
            content = pack.text
        out.append({"role": role, "content": content})
    return out


async def run_agent(payload: ChatRequest) -> AsyncIterator[dict[str, Any]]:
    loc: Location = payload.location or resolve_location(None)
    original = payload.message or ""
    incoming = await mt_inbound(original, payload.locale_hint)
    message_en = incoming.text or original
    locale = incoming.src if incoming.src not in {"auto", ""} else detect_lang(original, payload.locale_hint)
    out_locale = pick_output_locale(
        output_locale=payload.output_locale,
        locale_hint=payload.locale_hint,
        detected=locale,
    )
    snap_locale = out_locale if out_locale in {"en", "hi", "bn"} else "en"

    intent = classify(message_en)
    if intent == "general":
        intent = classify(original)
    place = mentioned_place(message_en) or mentioned_place(original)
    if place:
        loc = resolve_location(q=place)
    state = extract_state(message_en) or extract_state(original)
    if not state and intent in {"rank", "list", "price", "flood"}:
        state = loc.state
    metric = extract_metric(message_en)
    if metric == "flood":
        alt = extract_metric(original)
        if alt != "flood":
            metric = alt
    speech = observe_speech(original)

    yield {
        "type": "meta",
        "locale": locale,
        "output_locale": out_locale,
        "intent": intent,
        "state": state,
        "metric": metric,
        "location": loc.model_dump(),
        "translation": {"inbound": incoming.as_dict()},
        "vernacular": speech,
    }
    if incoming.engine not in {"identity", "disabled"} and incoming.ok:
        yield {
            "type": "notice",
            "message": f"Translated question {incoming.src} → en ({incoming.engine}).",
        }

    snap = await build_snapshot(loc, snap_locale)
    views = snapshot_tool_views(snap)
    yield {"type": "widget_patch", "path": "dashboard", "value": snap.model_dump()}

    extra: dict[str, Any] = {}
    reg = build_registry(snap, extra)
    traces: list[dict[str, Any]] = []
    tool_payloads: list[Any] = [views]
    collected: dict[str, Any] = {}

    async def exec_tool(name: str, args: dict[str, Any]) -> dict[str, Any]:
        t0 = time.perf_counter()
        start = {"type": "tool_start", "name": name, "args": args}
        try:
            result = await reg.call(name, args or {})
            status = "ok"
        except Exception as exc:
            result = {"error": str(exc)}
            status = "error"
        ms = int((time.perf_counter() - t0) * 1000)
        traces.append({"name": name, "status": status, "ms": ms})
        return {"start": start, "result": result, "ms": ms}

    for name in required_tools(intent):
        args = _tool_args(name, loc, state, metric, message_en)
        if name == "get_nowcast":
            args["speech"] = original
        pack = await exec_tool(name, args)
        yield pack["start"]
        yield {"type": "tool_result", "name": name, "data": pack["result"], "ms": pack["ms"]}
        tool_payloads.append(pack["result"])
        collected[name] = pack["result"]
        if isinstance(pack["result"], dict) and pack["result"].get("widget"):
            yield {"type": "widget_patch", "path": pack["result"]["widget"], "value": pack["result"]}

    grounded, template_id, slots = primary_reply(snap, snap_locale, intent)
    grounded_en, _, _ = primary_reply(snap, "en", intent)

    english_llm = ""
    ollama_ok, ollama_msg = await ollama_client.ping()
    if ollama_ok:
        try:
            messages: list[dict[str, Any]] = [{"role": "system", "content": SYSTEM}]
            messages.extend(await _english_history(payload.history))
            messages.append(
                {
                    "role": "user",
                    "content": (
                        f"Question: {message_en}\n"
                        f"Intent={intent} state={state} metric={metric}\n"
                        f"Speech tags (not numbers): {speech.get('tags') or []}\n"
                        f"Focus district: {snap.location.label}\n"
                        f"Tool results JSON:\n{json.dumps(_compact_tools(collected) or views, ensure_ascii=False)[:12000]}\n"
                        "If you still need a tool (rank_districts, list_districts, get_state_mandi, "
                        "compare_districts, predict_district), call it now. "
                        "Otherwise write a full original answer that lists names and tool numbers."
                    ),
                }
            )
            schemas = reg.openai_schemas()
            rounds = 0
            while rounds < 3:
                resp = await ollama_client.chat(messages, tools=schemas)
                calls = resp.get("tool_calls") or []
                if not calls:
                    english_llm = (resp.get("content") or "").strip()
                    break
                messages.append(
                    {
                        "role": "assistant",
                        "content": resp.get("content") or "",
                        "tool_calls": [
                            {
                                "id": c.get("id") or f"c{rounds}{i}",
                                "type": "function",
                                "function": {
                                    "name": c.get("name"),
                                    "arguments": c.get("arguments") or "{}",
                                },
                            }
                            for i, c in enumerate(calls)
                        ],
                    }
                )
                for c in calls:
                    name = c.get("name") or ""
                    args = _parse_args(c.get("arguments"))
                    if name not in reg.tools:
                        tool_out = {"error": f"unknown tool {name}"}
                        yield {"type": "tool_start", "name": name, "args": args}
                        yield {"type": "tool_result", "name": name, "data": tool_out, "ms": 0}
                    else:
                        if name in {"rank_districts", "list_districts", "get_state_mandi"} and not args.get("state"):
                            args["state"] = state or loc.state
                        pack = await exec_tool(name, args)
                        yield pack["start"]
                        yield {"type": "tool_result", "name": name, "data": pack["result"], "ms": pack["ms"]}
                        tool_out = pack["result"]
                        collected[name] = tool_out
                        if isinstance(tool_out, dict) and tool_out.get("widget") == "dashboard" and extra.get("snap"):
                            snap = extra["snap"]
                            loc = snap.location
                            extra.clear()
                            extra["snap"] = snap
                            reg = build_registry(snap, extra)
                            yield {"type": "widget_patch", "path": "dashboard", "value": snap.model_dump()}
                        elif isinstance(tool_out, dict) and tool_out.get("widget"):
                            yield {"type": "widget_patch", "path": tool_out["widget"], "value": tool_out}
                    tool_payloads.append(tool_out)
                    messages.append(
                        {
                            "role": "tool",
                            "tool_call_id": c.get("id") or "x",
                            "content": json.dumps(tool_out, ensure_ascii=False)[:8000],
                        }
                    )
                rounds += 1

            # Always generate a free-form answer after tools — this is the product.
            messages.append(
                {
                    "role": "user",
                    "content": (
                        "Write the final answer now. Do not call tools. "
                        "Use only the tool JSON above. Name districts. "
                        "If rank_districts ran, list them in order with flood_score / precip_3d_mm."
                    ),
                }
            )
            final_resp = await ollama_client.chat(messages, tools=None)
            english_llm = (final_resp.get("content") or english_llm or "").strip()
        except Exception as exc:
            yield {"type": "notice", "message": f"Tool-loop error ({exc}); generating without tools."}
            try:
                fallback = await ollama_client.chat(
                    [
                        {"role": "system", "content": SYSTEM},
                        {
                            "role": "user",
                            "content": (
                                f"Question: {message_en}\n"
                                f"Tool JSON:\n{json.dumps(_compact_tools(collected) or views, ensure_ascii=False)[:12000]}\n"
                                "Write a complete original answer. Name districts and quote the numbers."
                            ),
                        },
                    ],
                    tools=None,
                )
                english_llm = (fallback.get("content") or "").strip()
            except Exception as exc2:
                english_llm = ""
                yield {"type": "notice", "message": f"Ollama error: {exc2}"}
    else:
        yield {
            "type": "notice",
            "message": f"Ollama not reachable ({ollama_msg}). Start `ollama serve` with qwen2.5.",
        }

    if extra.get("snap"):
        snap = extra["snap"]
        grounded, template_id, slots = primary_reply(snap, snap_locale, intent)
        grounded_en, _, _ = primary_reply(snap, "en", intent)

    content_en = english_llm or grounded_en
    content_en = _ensure_ranking(content_en, collected)
    content_en, bad = lock_and_note(content_en, tool_payloads)
    if bad:
        yield {"type": "notice", "message": f"Model used extra numbers (kept): {bad[:8]}"}

    structured = compose_indic(out_locale, intent, snap, collected) if out_locale in {"hi", "bn"} else None
    content = content_en if content_en else grounded
    engine = "llm-en" if english_llm else "template-fallback"
    outbound = None
    if out_locale != "en" and content_en:
        outbound = await mt_outbound(content_en, out_locale)
        if outbound.ok and outbound.text:
            _, extra_nums = lock_and_note(
                outbound.text, tool_payloads + [content_en, structured or "", grounded]
            )
            content = outbound.text
            engine = f"llm-en+{outbound.engine}"
            yield {
                "type": "notice",
                "message": f"Translated answer en → {out_locale} ({outbound.engine}).",
            }
            if extra_nums:
                yield {"type": "notice", "message": f"Indic render extra numbers (kept): {extra_nums[:6]}"}
        elif structured:
            content = structured
            engine = "indic-compose"
            yield {"type": "notice", "message": f"MT unavailable ({outbound.engine}); used structured Indic."}
        else:
            content = content_en or grounded
            engine = "en-fallback"
            yield {"type": "notice", "message": f"MT unavailable ({outbound.engine}); showing English."}
    msg_id = uuid.uuid4().hex[:12]
    final = {
        "id": msg_id,
        "role": "assistant",
        "content": content,
        "content_en": content_en,
        "locale": out_locale,
        "tool_trace": traces,
        "citations": [
            {"tool": "rank_districts", "field": "ranked", "value": (collected.get("rank_districts") or {}).get("count")},
            {"tool": "get_weather_forecast", "field": "precip_next_3d_mm", "value": snap.predictive.precip_next_3d_mm},
        ],
        "translation": {
            "engine": engine,
            "src": "en",
            "tgt": out_locale,
            "inbound": incoming.as_dict(),
            "outbound": outbound.as_dict() if outbound else {"src": "en", "tgt": out_locale, "engine": engine, "ok": out_locale == "en"},
            "template_id": template_id,
            "slots": slots,
        },
    }
    yield {"type": "final", "message": final}

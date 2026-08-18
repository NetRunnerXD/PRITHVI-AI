from __future__ import annotations

import json
import re
import time
import uuid
from collections.abc import AsyncIterator
from typing import Any

from app.agents.binder import looks_like_dump
from app.agents.claims import check_claims
from app.agents.data_tool import (
    SCHEMA as DATA_SCHEMA,
    DataLib,
    attachments_for,
    parse_text_call,
    suggestions_for,
)
from app.agents.dates import parse_window
from app.agents.dimensions import extract_compare_other, mentioned_place
from app.data.india_districts import match_states
from app.agents.facts import (
    drop_false_shrug,
    fill_slots,
    is_pushback,
    needed_facts,
    prose_has_payload_number,
    quote_facts,
    rank_metric,
    source_gate,
    strip_unasked_pin,
)
from app.agents.utterance import (
    CATALOG_NEEDS,
    interpret,
    is_blocked_name,
    is_followup_affirm,
    looks_like_bare_place,
    wants_catalog,
)
from app.agents.memory import TurnState, load as mem_load, save as mem_save
from app.agents.prompts import SYSTEM
from app.agents.views import strip_forbidden
from app.i18n.detect import detect_lang, pick_output_locale
from app.i18n.mt import inbound as mt_inbound, outbound as mt_outbound
from app.llm import ollama_client
from app.schemas.chat import ChatRequest
from app.schemas.location import Location
from app.services.location_svc import resolve_india_place, resolve_location, resolve_named_place

_FOLLOW = re.compile(
    r"\b(there|same|that place|same for|what about|and the|how about|and tomorrow)\b",
    re.I,
)


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


async def _english_history(history: list[Any] | None) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    for h in (history or [])[-6:]:
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


def _iso_window(message: str) -> dict[str, str] | None:
    win = parse_window(message)
    if not win:
        return None
    start, end = win.get("start"), win.get("end")
    return {
        "start": start.isoformat() if hasattr(start, "isoformat") else str(start),
        "end": end.isoformat() if hasattr(end, "isoformat") else str(end),
        "kind": str(win.get("kind") or ""),
    }


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

    prior = mem_load(payload.conversation_id)
    plan = interpret(message_en)
    place = plan.asked or mentioned_place(message_en) or mentioned_place(original)
    resolved = resolve_named_place(place) if place else None
    inherit = bool(
        prior
        and prior.location
        and not resolved
        and (
            plan.follow
            or plan.catalog
            or is_followup_affirm(message_en)
            or (
                (_FOLLOW.search(message_en) or len(message_en.split()) <= 6)
                and not place
            )
        )
    )
    if (
        resolved is None
        and place
        and not is_blocked_name(place)
        and not plan.follow
        and not is_followup_affirm(message_en)
        and (plan.needs_geocode or looks_like_bare_place(message_en) or plan.mode == "data")
    ):
        try:
            resolved = await resolve_india_place(place)
        except Exception:
            resolved = None
        if resolved:
            plan.mode = "data"
            plan.unknown_place = False
            plan.needs_geocode = False
            plan.refuse = None
            if not plan.needs:
                plan.needs = ["forecast"]
        elif plan.needs_geocode or looks_like_bare_place(message_en):
            from app.agents.utterance import unknown_refuse

            plan.mode = "refuse"
            plan.unknown_place = True
            plan.refuse = unknown_refuse(place)
            plan.needs = []
    if resolved:
        loc = resolved
    elif inherit:
        try:
            loc = Location.model_validate(prior.location)
            place = place or prior.asked or loc.place_name or loc.district
        except Exception:
            inherit = False

    window_hint = _iso_window(message_en) or _iso_window(original)
    gate = source_gate(message_en)
    if plan.mode == "refuse" and plan.refuse:
        gate.mode = "refuse"
        gate.refuse = plan.refuse
        gate.needs = []
    elif plan.mode == "data" and plan.needs:
        gate.mode = "data"
        gate.needs = list(plan.needs)
        gate.states = list(plan.states)
    if gate.mode == "chat" and original != message_en:
        alt = source_gate(original)
        if alt.mode != "chat":
            gate = alt
    needed = list(gate.needs)
    if prior and prior.last_refuse and (
        is_pushback(message_en) or is_followup_affirm(message_en)
    ) and gate.mode != "data":
        gate.mode = "refuse"
        gate.refuse = prior.last_refuse
        needed = []
    if (
        inherit
        and prior
        and not prior.last_refuse
        and (plan.follow or plan.catalog or is_followup_affirm(message_en) or wants_catalog(message_en))
        and (prior.asked or prior.collected_keys or prior.catalog)
    ):
        have = {str(k).split(":")[0] for k in (prior.collected_keys or [])}
        remaining = [n for n in CATALOG_NEEDS if n not in have]
        gate.mode = "data"
        gate.needs = remaining or list(CATALOG_NEEDS)
        needed = list(gate.needs)
        plan.catalog = True
        plan.follow = True
    if plan.catalog and not needed and (resolved or inherit):
        gate.mode = "data"
        gate.needs = list(CATALOG_NEEDS)
        needed = list(gate.needs)
    if (plan.catalog or plan.follow) and not resolved and not inherit and not place:
        # "all of them" / "yes" with no prior town — do not dump the dashboard pin.
        gate.mode = "chat"
        gate.needs = []
        needed = []
        plan.catalog = False
    if (
        gate.mode == "chat"
        and prior
        and prior.collected_keys
        and _FOLLOW.search(message_en)
    ):
        more_states = match_states(message_en)
        if more_states and any(str(k).startswith("rank") or k == "rank" for k in prior.collected_keys):
            gate.mode = "data"
            gate.needs = ["rank"]
            gate.states = more_states
            needed = ["rank"]
    if gate.mode == "refuse" and gate.refuse:
        mem_save(
            payload.conversation_id,
            TurnState(
                location=loc.model_dump(),
                question_en=message_en,
                content_en=gate.refuse,
                last_refuse=gate.refuse,
                asked=prior.asked if prior else None,
                catalog=bool(prior.catalog) if prior else False,
            ),
        )
        yield {
            "type": "meta",
            "locale": locale,
            "output_locale": out_locale,
            "location": loc.model_dump(),
            "question_en": message_en,
            "window": window_hint,
            "needed": [],
            "gate": "refuse",
            "translation": {"inbound": incoming.as_dict()},
        }
        msg_id = uuid.uuid4().hex[:12]
        yield {
            "type": "final",
            "message": {
                "id": msg_id,
                "role": "assistant",
                "content": gate.refuse,
                "content_en": gate.refuse,
                "locale": out_locale,
                "blocks": [],
                "suggestions": [],
                "tool_trace": [],
                "citations": [],
                "translation": {
                    "engine": "source-gate",
                    "src": "en",
                    "tgt": out_locale,
                    "inbound": incoming.as_dict(),
                    "outbound": {"src": "en", "tgt": out_locale, "engine": "source-gate", "ok": True},
                },
            },
        }
        return

    yield {
        "type": "meta",
        "locale": locale,
        "output_locale": out_locale,
        "location": loc.model_dump(),
        "question_en": message_en,
        "window": window_hint,
        "needed": needed,
        "translation": {"inbound": incoming.as_dict()},
    }
    if incoming.engine not in {"identity", "disabled"} and incoming.ok:
        yield {
            "type": "notice",
            "message": f"Translated question {incoming.src} → en ({incoming.engine}).",
        }

    lib = DataLib(loc, speech=original)
    traces: list[dict[str, Any]] = []
    collected: dict[str, Any] = {}

    async def exec_data(args: dict[str, Any]) -> dict[str, Any]:
        need = str(args.get("need") or "")
        if need == "rain_window" and window_hint:
            args.setdefault("start", window_hint.get("start"))
            args.setdefault("end", window_hint.get("end"))
        if need == "rain_window" and not args.get("place"):
            args["place"] = loc.place_name or loc.district
        t0 = time.perf_counter()
        yield_start = {"type": "tool_start", "name": "data", "args": {"need": need, **{k: args[k] for k in args if k != "need"}}}
        try:
            result = await lib.call(args)
            status = "ok"
        except Exception as exc:
            result = {"error": str(exc), "need": need}
            status = "error"
        ms = int((time.perf_counter() - t0) * 1000)
        traces.append({"name": f"data:{need}", "status": status, "ms": ms})
        key = need or "data"
        collected[key] = strip_forbidden(result)
        if lib.snap is not None:
            loc_ref = lib.loc
        else:
            loc_ref = loc
        return {"start": yield_start, "result": collected[key], "ms": ms, "loc": loc_ref}

    prefetch_bare = bool(
        needed
        and (resolved or inherit)
        and (
            looks_like_bare_place(message_en)
            or needed == ["forecast"]
            or plan.catalog
            or plan.follow
            or len(needed) >= 3
        )
    )
    if prefetch_bare:
        for need in list(needed):
            if need in collected:
                continue
            pack = await exec_data(
                {"need": need, "place": loc.place_name or loc.district, "question": message_en}
            )
            yield pack["start"]
            yield {"type": "tool_result", "name": "data", "data": pack["result"], "ms": pack["ms"]}
            loc = pack["loc"]

    english_llm = ""
    ollama_ok, ollama_msg = await ollama_client.ping()
    if ollama_ok:
        try:
            messages: list[dict[str, Any]] = [{"role": "system", "content": SYSTEM}]
            messages.extend(await _english_history(payload.history))
            hint_bits = []
            if window_hint:
                hint_bits.append(f"Named dates (use only if you call rain_window): {window_hint['start']} to {window_hint['end']}.")
            if place:
                hint_bits.append(
                    f"The user named {place} ({loc.label}). Describe only that place. "
                    "Do not mention any other dashboard pin. "
                    "Do not say you could not find data if figures are provided below."
                )
            else:
                hint_bits.append("No new town was named. Do not drag in an unrelated pin.")
            pre_quote = quote_facts(collected)
            if pre_quote:
                hint_bits.append("Already fetched:\n" + pre_quote)
            messages.append(
                {
                    "role": "user",
                    "content": (
                        f"Question: {message_en}\n"
                        + ("\n".join(hint_bits) + "\n")
                        + "Reply as chat. Call data() if you need a Rituchakra number for the named place."
                    ),
                }
            )
            rounds = 0
            nudged = False
            while rounds < 5:
                resp = await ollama_client.chat(messages, tools=[DATA_SCHEMA])
                if resp.get("tools_stripped"):
                    yield {"type": "notice", "message": "Ollama rejected tool schemas; reading a text data: line if present."}
                    line = parse_text_call(resp.get("content") or "")
                    if line:
                        pack = await exec_data(line)
                        yield pack["start"]
                        yield {"type": "tool_result", "name": "data", "data": pack["result"], "ms": pack["ms"]}
                        loc = pack["loc"]
                        messages.append({"role": "assistant", "content": resp.get("content") or ""})
                        messages.append(
                            {
                                "role": "user",
                                "content": f"data result:\n{json.dumps(pack['result'], ensure_ascii=False)[:8000]}\nNow answer the question in ordinary English. No tool names.",
                            }
                        )
                        rounds += 1
                        continue
                calls = resp.get("tool_calls") or []
                if not calls:
                    english_llm = (resp.get("content") or "").strip()
                    line = parse_text_call(english_llm)
                    if line:
                        pack = await exec_data(line)
                        yield pack["start"]
                        yield {"type": "tool_result", "name": "data", "data": pack["result"], "ms": pack["ms"]}
                        loc = pack["loc"]
                        messages.append({"role": "assistant", "content": english_llm})
                        messages.append(
                            {
                                "role": "user",
                                "content": f"data result:\n{json.dumps(pack['result'], ensure_ascii=False)[:8000]}\nNow answer in ordinary English.",
                            }
                        )
                        english_llm = ""
                        rounds += 1
                        continue
                    if needed and not collected and not nudged:
                        nudged = True
                        messages.append({"role": "assistant", "content": english_llm})
                        messages.append(
                            {
                                "role": "user",
                                "content": (
                                    "This question needs Rituchakra figures. "
                                    f"Call data() now with need in {needed}. Then quote those numbers."
                                ),
                            }
                        )
                        english_llm = ""
                        rounds += 1
                        continue
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
                    args = _parse_args(c.get("arguments"))
                    name = c.get("name") or ""
                    if name != "data":
                        tool_out: Any = {"error": "only the data function is available"}
                        yield {"type": "tool_start", "name": name, "args": args}
                        yield {"type": "tool_result", "name": name, "data": tool_out, "ms": 0}
                    else:
                        pack = await exec_data(args)
                        yield pack["start"]
                        yield {"type": "tool_result", "name": "data", "data": pack["result"], "ms": pack["ms"]}
                        loc = pack["loc"]
                        tool_out = pack["result"]
                    messages.append(
                        {
                            "role": "tool",
                            "tool_call_id": c.get("id") or "x",
                            "content": json.dumps(tool_out, ensure_ascii=False)[:8000],
                        }
                    )
                rounds += 1
        except Exception as exc:
            yield {"type": "notice", "message": f"Chat loop error ({exc})."}
            try:
                fallback = await ollama_client.chat(
                    [
                        {"role": "system", "content": SYSTEM},
                        {
                            "role": "user",
                            "content": (
                                f"Question: {message_en}\n"
                                f"Data this turn:\n{json.dumps(strip_forbidden(collected), ensure_ascii=False)[:8000]}\n"
                                "Answer in 2–4 English sentences. No digits unless they appear in the data."
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

    if looks_like_dump(english_llm):
        english_llm = ""
        if ollama_ok:
            try:
                retry = await ollama_client.chat(
                    [
                        {"role": "system", "content": SYSTEM},
                        {
                            "role": "user",
                            "content": (
                                f"Question: {message_en}\n"
                                f"Data this turn:\n{json.dumps(strip_forbidden(collected), ensure_ascii=False)[:8000]}\n"
                                "Answer the user in 2–4 sentences. No digits unless they appear above. No JSON."
                            ),
                        },
                    ],
                    tools=None,
                )
                english_llm = (retry.get("content") or "").strip()
                if looks_like_dump(english_llm):
                    english_llm = ""
            except Exception:
                english_llm = ""

    for need in needed:
        if need == "rank" and gate.states:
            for st in gate.states:
                key = f"rank:{st}"
                if key in collected or (need in collected and collected[need].get("state") == st):
                    continue
                pack = await exec_data({"need": "rank", "state": st, "question": message_en, "metric": rank_metric(message_en)})
                yield pack["start"]
                yield {"type": "tool_result", "name": "data", "data": pack["result"], "ms": pack["ms"]}
                collected[key] = pack["result"]
                loc = pack["loc"]
            continue
        if need in collected:
            continue
        args: dict[str, Any] = {
            "need": need,
            "place": loc.place_name or loc.district,
            "question": message_en,
        }
        if need == "compare":
            other = extract_compare_other(message_en, loc.place_name or loc.district)
            if not other:
                continue
            args["other"] = other
        if need == "rank" and gate.states:
            args["state"] = gate.states[0]
        pack = await exec_data(args)
        yield pack["start"]
        yield {"type": "tool_result", "name": "data", "data": pack["result"], "ms": pack["ms"]}
        loc = pack["loc"]

    payloads = list(collected.values())
    content_en, rejected = check_claims(english_llm, payloads)
    asked_name = place or (prior.asked if prior else None) or (loc.place_name if inherit else None)
    pin_from_client = (payload.location.label if payload.location else None)
    content_en = strip_unasked_pin(content_en, asked_name, pin_from_client)
    content_en = fill_slots(content_en, collected)
    content_en = drop_false_shrug(content_en, collected)
    quoted = quote_facts(collected)
    if quoted and not prose_has_payload_number(content_en, collected):
        content_en = f"{content_en}\n\n{quoted}".strip() if content_en else quoted
    if not content_en:
        if collected:
            content_en = quoted or "Here is what Rituchakra has for that."
        else:
            content_en = (
                "I can chat about Indian weather, flood, heat, air, marine, quake watches, mandi prices, "
                "and field decisions — and I can look up real figures when you need them. "
                "What would you like to know?"
            )

    if rejected and rejected != ["dump"]:
        yield {"type": "notice", "message": f"Ungrounded figures replaced: {rejected[:8]}"}

    blocks = attachments_for(collected)
    suggestions = suggestions_for(collected, loc)
    if suggestions:
        yield {"type": "suggestions", "suggestions": suggestions}

    content = content_en
    engine = "llm-en" if english_llm else "chat-fallback"
    outbound = None
    if out_locale != "en" and content_en:
        outbound = await mt_outbound(content_en, out_locale)
        if outbound.ok and outbound.text and not looks_like_dump(outbound.text):
            content = outbound.text
            engine = f"llm-en+{outbound.engine}"
            yield {"type": "notice", "message": f"Translated answer en → {out_locale} ({outbound.engine})."}
        else:
            engine = "en-fallback"
            yield {"type": "notice", "message": "Showing English (translation unavailable)."}

    mem_save(
        payload.conversation_id,
        TurnState(
            location=loc.model_dump(),
            dimensions=None,
            collected_keys=list(collected),
            question_en=message_en,
            content_en=content_en,
            last_refuse=None,
            asked=(
                (place or loc.place_name)
                if resolved
                else (prior.asked if prior and inherit else None)
            ),
            catalog=bool(plan.catalog or (prior.catalog if prior and inherit else False)),
        ),
    )

    msg_id = uuid.uuid4().hex[:12]
    final = {
        "id": msg_id,
        "role": "assistant",
        "content": content,
        "content_en": content_en,
        "locale": out_locale,
        "blocks": blocks,
        "suggestions": suggestions,
        "tool_trace": traces,
        "citations": [{"tool": k, "field": "need", "value": (v or {}).get("need") if isinstance(v, dict) else k} for k, v in collected.items()],
        "translation": {
            "engine": engine,
            "src": "en",
            "tgt": out_locale,
            "inbound": incoming.as_dict(),
            "outbound": outbound.as_dict()
            if outbound
            else {"src": "en", "tgt": out_locale, "engine": engine, "ok": out_locale == "en"},
        },
    }
    yield {"type": "final", "message": final}

from __future__ import annotations

import json
import re
import time
import uuid
from collections.abc import AsyncIterator
from typing import Any

from app.agents.binder import looks_like_dump
from app.agents.counterfactual import detect_scale, scale_forecast
from app.agents.graph import route as graph_route
from app.agents.ledger import ledger_for
from app.agents.post import BEYOND_SKILL, hedge, severity
from app.agents.resolved import as_dict as resolved_dict
from app.agents.resolved import build as build_resolved
from app.agents.triage import classify as triage_classify
from app.agents.claims import check_claims
from app.agents.data_tool import (
    SCHEMA as DATA_SCHEMA,
    DataLib,
    attachments_for,
    parse_text_call,
    strip_tool_syntax,
    suggestions_for,
)
from app.agents.dates import parse_window
from app.agents.dimensions import detect_domain, extract_compare_other, mentioned_place
from app.data.india_districts import match_states
from app.agents.facts import (
    drop_false_shrug,
    fill_slots,
    has_null_metrics,
    is_dash_soup,
    is_pushback,
    present_answer,
    prose_has_payload_number,
    quote_facts,
    rank_metric,
    source_gate,
    strip_foreign_places,
    strip_unasked_pin,
)
from app.agents.utterance import (
    CATALOG_NEEDS,
    interpret,
    is_blocked_name,
    is_followup_affirm,
    is_time_followup,
    looks_like_bare_place,
    wants_catalog,
)
from app.data.closed_class import is_closed_query
from app.agents.memory import TurnState, load as mem_load, save as mem_save
from app.agents.prompts import GEMINI_NATIVE_DELTA, INSIGHT_SYSTEM_DELTA, SYSTEM
from app.agents.views import strip_forbidden
from app.i18n.detect import detect_lang, has_script, pick_output_locale, script_of
from app.i18n.gemini_langs import gemini_native
from app.i18n.mt import inbound as mt_inbound, outbound as mt_outbound
from app.i18n.mt import MTResult
from app.i18n.number_lock import NUM
from app.llm import ollama_client
from app.schemas.chat import ChatRequest
from app.schemas.location import Location
from app.services.location_svc import resolve_india_place, resolve_location, resolve_named_place
from app.agents.orch_place import (
    _bind_focus_place,
    _fold_hit,
    _iso_window,
    _place_matches_locus,
    _same_pin,
)
from app.agents.orch_locale import (
    _english_history,
    _llm_translate,
    _localize_validated,
    _mt_kept_numbers,
    _usable_translation,
)

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


async def run_agent(payload: ChatRequest) -> AsyncIterator[dict[str, Any]]:
    llm_tok = ollama_client.use_provider(payload.llm)
    try:
        async for ev in _run_agent(payload):
            yield ev
    finally:
        ollama_client.reset_provider(llm_tok)


async def _run_agent(payload: ChatRequest) -> AsyncIterator[dict[str, Any]]:
    pin_now: Location = payload.location or resolve_location(None)
    loc: Location = pin_now
    if payload.om:
        from app.providers import open_meteo as om_mod

        om_mod.seed_from_client(loc.lat, loc.lon, payload.om, payload.fetched_at)
    original = payload.message or ""
    detected0 = detect_lang(original, payload.locale_hint)
    llm_id = (payload.llm or "").strip().lower()
    if not llm_id:
        from app.llm.providers import resolve as resolve_llm

        llm_id = resolve_llm().id
    native_in = llm_id == "gemini" and gemini_native(detected0) and detected0 != "en"
    if native_in:
        incoming = MTResult(text=original, src=detected0 or "en", tgt="en", engine="gemini-native", ok=True)
    else:
        incoming = await mt_inbound(original, payload.locale_hint)
    locale = incoming.src if incoming.src not in {"auto", ""} else detected0
    if incoming.ok:
        message_en = incoming.text or original
    elif locale != "en":
        message_en = (
            f"(User language is {locale}; translate the meaning into an English weather question, "
            f"then answer in English.)\n{original}"
        )
    else:
        message_en = original
    message_en, mt_place = _bind_focus_place(original, message_en, pin_now)
    out_locale = pick_output_locale(
        output_locale=payload.output_locale,
        locale_hint=payload.locale_hint,
        detected=locale,
    )
    native_gemini = llm_id == "gemini" and gemini_native(out_locale) and out_locale != "en"

    prior = mem_load(payload.conversation_id)
    history_en = await _english_history(payload.history)

    # Layer 1: Semantic Context & Entity Extraction (Hybrid 2-Layer Pipeline)
    from app.agents.layer1_parser import parse_semantic_context
    layer1_ctx = await parse_semantic_context(
        message_en,
        history_en=history_en,
        default_loc=loc,
        prior_window=prior.window if prior else None,
    )
    domain = layer1_ctx.domain
    activity = layer1_ctx.activity
    insight_turn = False
    insight_packet = None

    plan = interpret(message_en)
    tri = triage_classify(message_en, plan)
    if tri.kind == "emergency":
        yield {
            "type": "meta",
            "locale": locale,
            "output_locale": out_locale,
            "location": loc.model_dump(),
            "question_en": message_en,
            "triage": "emergency",
            "needed": [],
            "gate": "emergency",
        }
        em_en = tri.message
        em, em_out, em_engine = await _localize_validated(em_en, out_locale, native=native_gemini)
        yield {
            "type": "final",
            "message": {
                "id": uuid.uuid4().hex[:12],
                "role": "assistant",
                "content": em,
                "content_en": em_en,
                "locale": out_locale,
                "blocks": [],
                "suggestions": [],
                "tool_trace": [],
                "citations": [],
                "triage": "emergency",
                "translation": {
                    "engine": em_engine,
                    "src": "en",
                    "tgt": out_locale,
                    "inbound": incoming.as_dict(),
                    "outbound": em_out.as_dict() if em_out else {"src": "en", "tgt": out_locale, "engine": "identity", "ok": True},
                },
            },
        }
        return

    place = mt_place or plan.asked or mentioned_place(message_en) or mentioned_place(original)
    if layer1_ctx.place_resolved and not is_blocked_name(layer1_ctx.place_raw or ""):
        resolved = layer1_ctx.place_resolved
        place = layer1_ctx.place_raw or resolved.place_name
        plan.asked = place
        plan.unknown_place = False
        plan.needs_geocode = False
        if plan.mode == "refuse":
            plan.mode = "data"
            plan.refuse = None
        if not plan.needs and layer1_ctx.intent in ("forecast", "activity_feasibility"):
            plan.needs = ["forecast", "rain_window"]
        if not plan.needs and layer1_ctx.intent == "warnings":
            plan.needs = ["warnings", "risks"]
    else:
        resolved = None

    if place and script_of(original) and not mentioned_place(original) and not _place_matches_locus(place, pin_now, None):
        place = None
        plan.asked = None
        plan.needs_geocode = False
    if place and (is_closed_query(place) or is_time_followup(message_en)):
        place = None
        plan.asked = None
        plan.needs_geocode = False
        plan.follow = True
    if not resolved:
        resolved = resolve_named_place(place) if place else None
    prior_pin = None
    if prior and prior.pin:
        try:
            prior_pin = Location.model_validate(prior.pin)
        except Exception:
            prior_pin = None
    pin_moved = bool(prior_pin is not None and not _same_pin(pin_now, prior_pin))
    inherit = bool(
        prior
        and prior.location
        and not resolved
        and not pin_moved
        and (
            plan.follow
            or plan.catalog
            or is_followup_affirm(message_en)
            or is_time_followup(message_en)
            or (
                (_FOLLOW.search(message_en) or len(message_en.split()) <= 6)
                and not place
            )
        )
    )
    from app.data.closed_class import is_closed_token

    if place and (is_closed_query(place) or is_closed_token(place)):
        place = None
        plan.asked = None
        plan.needs_geocode = False
    if (
        resolved is None
        and place
        and not is_blocked_name(place)
        and not plan.follow
        and not is_followup_affirm(message_en)
        and not is_time_followup(message_en)
        and not is_closed_query(place)
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

    this_window = _iso_window(message_en) or _iso_window(original)
    window_hint = this_window
    if window_hint is None and inherit and prior and prior.window:
        window_hint = dict(prior.window)
    if this_window is None and resolved and prior and prior.window and not pin_moved:
        # New place, same dates as last turn unless the user named new ones.
        window_hint = dict(prior.window)
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
        and not is_time_followup(message_en)
        and (plan.catalog or is_followup_affirm(message_en) or wants_catalog(message_en))
        and (prior.asked or prior.collected_keys or prior.catalog)
    ):
        have = {str(k).split(":")[0] for k in (prior.collected_keys or [])}
        remaining = [n for n in CATALOG_NEEDS if n not in have]
        gate.mode = "data"
        gate.needs = remaining or list(CATALOG_NEEDS)
        needed = list(gate.needs)
        plan.catalog = True
        plan.follow = True
    if (
        inherit
        and prior
        and is_time_followup(message_en)
        and not needed
    ):
        prior_needs = list(prior.needs or [])
        rainish = any(
            n in prior_needs for n in ("rain_window", "forecast", "nowcast")
        ) or any(w in message_en.lower() for w in ("rain", "mm", "how much", "shower"))
        gate.mode = "data"
        if rainish or this_window:
            gate.needs = ["rain_window"]
        else:
            gate.needs = prior_needs or ["forecast"]
        needed = list(gate.needs)
        plan.follow = True
    if (
        resolved
        and prior
        and not this_window
        and not needed
        and prior.needs
        and looks_like_bare_place(message_en)
    ):
        gate.mode = "data"
        gate.needs = list(prior.needs)
        needed = list(gate.needs)
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
    needed, graph_peak = graph_route(message_en, needed)
    if gate.mode == "data" and graph_peak < 0.45 and not needed:
        needed = ["capability"]
        gate.needs = ["capability"]
    beyond = False
    if window_hint and window_hint.get("end"):
        from datetime import date, timedelta

        from app.agents.dates import today_ist

        try:
            end_d = date.fromisoformat(str(window_hint["end"])[:10])
            beyond = end_d > today_ist() + timedelta(days=16)
        except ValueError:
            beyond = False
    if beyond and "rain_window" in needed:
        needed = [n for n in needed if n != "rain_window"]
        gate.needs = list(needed)

    from app.agents.insight_compiler import insight_canary, insight_eligible
    from app.config import get_settings
    from app.llm.providers import select_narrator

    _settings = get_settings()
    insight_ok = insight_eligible(layer1_ctx, gate, tri, plan)
    insight_turn = insight_ok and insight_canary(
        payload.conversation_id, _settings.insight_chat_percent, _settings.insight_chat
    )
    if insight_turn:
        extra: list[str] = []
        intent = layer1_ctx.intent
        tone = getattr(layer1_ctx, "tone", "") or ""
        if intent == "aqi" or tone in {"worried", "health"}:
            extra.append("aqi")
        elif intent in {"nowcast"} or tone == "rushed":
            extra.extend(["nowcast", "forecast"])
        elif intent in {"forecast", "activity_feasibility"}:
            extra.append("forecast")
        if "flood" in message_en.lower():
            extra.append("risks")
        if any(w in message_en.lower() for w in ("heat", "wbgt", "hot")):
            extra.append("risks")
        for n in extra:
            if n not in needed:
                needed.append(n)
        gate.needs = list(needed)

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
                pin=pin_now.model_dump(),
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
        refuse_en = gate.refuse
        refuse, refuse_out, refuse_engine = await _localize_validated(refuse_en, out_locale, native=native_gemini)
        msg_id = uuid.uuid4().hex[:12]
        yield {
            "type": "final",
            "message": {
                "id": msg_id,
                "role": "assistant",
                "content": refuse,
                "content_en": refuse_en,
                "locale": out_locale,
                "blocks": [],
                "suggestions": [],
                "tool_trace": [],
                "citations": [],
                "translation": {
                    "engine": refuse_engine,
                    "src": "en",
                    "tgt": out_locale,
                    "inbound": incoming.as_dict(),
                    "outbound": refuse_out.as_dict()
                    if refuse_out
                    else {"src": "en", "tgt": out_locale, "engine": "source-gate", "ok": True},
                },
            },
        }
        return

    rq = build_resolved(
        message_en,
        loc,
        window=window_hint,
        inherited_place=bool(inherit),
        new_place=bool(resolved),
    )
    yield {
        "type": "meta",
        "locale": locale,
        "output_locale": out_locale,
        "location": loc.model_dump(),
        "question_en": message_en,
        "window": window_hint,
        "needed": needed,
        "triage": tri.kind,
        "resolved": resolved_dict(rq),
        "translation": {"inbound": incoming.as_dict()},
    }
    if incoming.engine not in {"identity", "disabled"} and incoming.ok:
        yield {
            "type": "notice",
            "message": f"Translated question {incoming.src} → en ({incoming.engine}).",
        }
    elif not incoming.ok and locale != "en":
        yield {
            "type": "notice",
            "message": f"Could not translate question {locale} → en ({incoming.engine}); LLM still answers in English.",
        }

    lib = DataLib(loc, speech=original)
    traces: list[dict[str, Any]] = []
    collected: dict[str, Any] = {}

    async def exec_data(args: dict[str, Any]) -> dict[str, Any]:
        args = dict(args)
        need = str(args.get("need") or "")
        if need in {"rain_window", "forecast"} and window_hint:
            args.setdefault("start", window_hint.get("start"))
            args.setdefault("end", window_hint.get("end"))
            if window_hint.get("hour") is not None:
                args.setdefault("hour", window_hint.get("hour"))
        skip_clamp = need in {"rank", "states_weather", "place_search", "capability"}
        if need == "mandi" and "mandi" not in needed:
            return {
                "start": {"type": "tool_start", "name": "data", "args": {"need": need, "skipped": "unasked"}},
                "result": {"need": need, "skipped": True},
                "ms": 0,
                "loc": loc,
            }
        if need == "states_weather" and "states_weather" not in needed and "rank" in needed:
            return {
                "start": {"type": "tool_start", "name": "data", "args": {"need": need, "skipped": "unasked"}},
                "result": {"need": need, "skipped": True},
                "ms": 0,
                "loc": loc,
            }
        requested = str(args.get("place") or "").strip()
        clamped_from = None
        if not skip_clamp:
            if not requested:
                args["place"] = loc.place_name or loc.district
            elif not _place_matches_locus(requested, loc, place):
                got = None
                try:
                    got = await resolve_india_place(requested)
                except Exception:
                    got = None
                if not (got and _same_pin(loc, got)):
                    clamped_from = requested
                    args["place"] = loc.place_name or loc.district
        t0 = time.perf_counter()
        shown = {k: args[k] for k in args if k != "need"}
        if clamped_from:
            shown["clamped_from"] = clamped_from
        yield_start = {"type": "tool_start", "name": "data", "args": {"need": need, **shown}}
        try:
            result = await lib.call(args)
            status = "ok"
        except Exception as exc:
            result = {"error": str(exc), "need": need}
            status = "error"
        ms = int((time.perf_counter() - t0) * 1000)
        trace: dict[str, Any] = {"name": f"data:{need}", "status": status, "ms": ms}
        if clamped_from:
            trace["clamped_from"] = clamped_from
        traces.append(trace)
        key = need or "data"
        collected[key] = strip_forbidden(result)
        return {"start": yield_start, "result": collected[key], "ms": ms, "loc": loc}

    if needed:
        for need in list(needed):
            if need == "rank" and gate.states:
                for st in gate.states:
                    key = f"rank:{st}"
                    if key in collected or (need in collected and collected[need].get("state") == st):
                        continue
                    pack = await exec_data(
                        {
                            "need": "rank",
                            "state": st,
                            "question": message_en,
                            "metric": rank_metric(message_en),
                        }
                    )
                    yield pack["start"]
                    yield {"type": "tool_result", "name": "data", "data": pack["result"], "ms": pack["ms"]}
                    collected[key] = pack["result"]
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

    english_llm = ""
    if insight_turn:
        want = select_narrator(payload, _settings, insight_turn=True)
        if want:
            ollama_client.use_provider(want)
    ollama_ok, ollama_msg = await ollama_client.ping()
    narrator = ollama_client._resolved()
    yield {
        "type": "notice",
        "message": f"Narrator {narrator.id}:{narrator.model}"
        + ("" if ollama_ok else f" (ping {ollama_msg}; still calling the model)"),
    }
    if not ollama_ok:
        ollama_ok = True
    if ollama_ok:
        try:
            sys_content = SYSTEM + ("\n" + INSIGHT_SYSTEM_DELTA if insight_turn else "")
            if native_gemini and out_locale != "en":
                sys_content = sys_content + GEMINI_NATIVE_DELTA.format(lang=out_locale)
            messages: list[dict[str, Any]] = [{"role": "system", "content": sys_content}]
            messages.extend(history_en)
            hint_bits = [
                f"User role / domain: {domain}. Vary wording; do not recycle a canned one-liner. "
                "Quote only digits that appear in the fact pack below. Do not invent millimetres, AQI, or risk %."
            ]
            if domain == "disaster":
                hint_bits.append(
                    "Format for an operations desk:\n"
                    "SITUATION — 2–4 sentences on what is happening at this pin.\n"
                    "HAZARDS — bullet list of active warnings and risk cards (severity + meaning).\n"
                    "ACTIONS — 2–4 concrete next steps (observe, move, hold, notify). "
                    "Never certify an all-clear."
                )
            else:
                hint_bits.append(
                    "Write a natural reply (about a short paragraph, or a few bullets if they asked for a list). "
                    "Lead with the asked hour or day if one was named. End with one useful action for this user, "
                    "phrased freshly from the numbers — not a stock irrigation/umbrella line."
                )
            if window_hint:
                w_start, w_end = window_hint.get("start"), window_hint.get("end")
                w_label = f"{w_start} to {w_end}" if w_start != w_end else str(w_start)
                clock_str = f" at {window_hint.get('hour')}:00" if window_hint.get("hour") else ""
                hint_bits.append(f"Named dates (use only if you call rain_window): {w_label}{clock_str}.")
                hint_bits.append(
                    f"SPECIFIC TIME OVERVIEW: The user asked about {w_label}{clock_str}. "
                    "Provide a brief card-overview-style snapshot of key metrics (temperature, rain probability/mm, wind/sky) "
                    "followed immediately by 1 actionable advice."
                )
            if "rank" in needed or "states_weather" in needed:
                st = ", ".join(gate.states) if gate.states else "the named state"
                hint_bits.append(
                    f"This is a ranking for {st}. Write a short numbered list of top 3 to 5 districts with their score. "
                    "Do not mention the dashboard town. Do not list other Indian states. "
                    "Do not mention mandi, crops, or markets. Conclude with 1 regional advisory line."
                )
            elif needed or tri.kind == "data":
                named = "named this town in the question" if place else "did not name a town — use only the dashboard/GPS focus"
                hint_bits.append(
                    f"Answer only for {loc.label} "
                    f"(focus {loc.place_name or loc.district}, district {loc.district}, {named}). "
                    "Do not mention Patna, Bihar, Haldia, or any other district unless it is this focus "
                    "or the user named it. Never switch state. "
                    "Do not say you could not find data if figures are provided below. "
                    "Do not invent dates or millimetres. Quote only the data() pack for this window. "
                    "Do not mention mandi or farm prices unless the user asked."
                )
            elif not needed and tri.kind != "data":
                hint_bits.append(
                    "This is chit-chat. Do not fetch weather. Do not mention a town unless the user named one. "
                    "Greet briefly and say you can look up Indian weather, flood, AQI, and nowcast when asked. "
                    "Do not mention mandi unless they ask."
                )
            if place:
                hint_bits.append(f"The user named {place}.")
            if layer1_ctx.tailored_user_hint:
                hint_bits.append(layer1_ctx.tailored_user_hint)
            if insight_turn:
                from app.agents.insight_compiler import compile_insight
                from app.services.snapshot import peek_snapshot

                snap = peek_snapshot(loc)
                insight_packet = compile_insight(
                    loc, collected, layer1_ctx, snap=snap
                )
                for extra_need in list(insight_packet.needs_extra):
                    if extra_need in collected:
                        continue
                    pack = await exec_data(
                        {
                            "need": extra_need,
                            "place": loc.place_name or loc.district,
                            "question": message_en,
                        }
                    )
                    yield pack["start"]
                    yield {"type": "tool_result", "name": "data", "data": pack["result"], "ms": pack["ms"]}
                if insight_packet.needs_extra:
                    insight_packet = compile_insight(loc, collected, layer1_ctx, snap=snap)
                hint_bits.append(
                    "Insight packet (band names only; quote raw_cite digits if you must use a number):\n"
                    + insight_packet.model_dump_json()
                )
                pre_quote = ""
            else:
                pre_quote = quote_facts(collected, window=window_hint)
                if pre_quote:
                    hint_bits.append(
                        "Verified fact pack (quote these figures; write original prose around them):\n" + pre_quote
                    )
            messages.append(
                {
                    "role": "user",
                    "content": (
                        f"Question: {message_en}\n"
                        + ("\n".join(hint_bits) + "\n")
                        + (
                            "Reply with the InsightReply JSON object only."
                            if insight_turn
                            else "Reply as chat. Call data() if you need a Prithvi AI number for the named place."
                        )
                    ),
                }
            )
            rounds = 0
            nudged = False
            use_tools = bool(needed) or tri.kind == "data"
            max_rounds = 2 if insight_turn else 5
            while rounds < max_rounds:
                resp = await ollama_client.chat(
                    messages,
                    tools=[DATA_SCHEMA] if use_tools else None,
                )
                if resp.get("tools_stripped"):
                    pid = str(resp.get("provider") or "model")
                    err = str(resp.get("error") or "").strip()[:120]
                    extra = f" ({err})" if err else ""
                    yield {
                        "type": "notice",
                        "message": f"{pid} dropped tools{extra}; answering from server-fetched packs.",
                    }
                    use_tools = False
                    xml_calls = []
                    from app.agents.data_tool import parse_xml_tool_calls

                    xml_calls = parse_xml_tool_calls(resp.get("content") or "")
                    if xml_calls:
                        resp = {**resp, "tool_calls": xml_calls, "content": ""}
                    else:
                        for need in list(needed):
                            if need in collected or need == "rank":
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
                            pack = await exec_data(args)
                            yield pack["start"]
                            yield {"type": "tool_result", "name": "data", "data": pack["result"], "ms": pack["ms"]}
                        facts = quote_facts(collected, window=window_hint) or json.dumps(
                            strip_forbidden(collected), ensure_ascii=False
                        )[:8000]
                        messages.append(
                            {
                                "role": "user",
                                "content": (
                                    "Function calling is off. Quote only these verified packs. "
                                    "Ordinary English. No tool names.\n"
                                    f"{facts}"
                                ),
                            }
                        )
                        english_llm = ""
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
                        messages.append({"role": "assistant", "content": english_llm})
                        if insight_turn:
                            from app.agents.insight_compiler import compile_insight
                            from app.services.snapshot import peek_snapshot

                            insight_packet = compile_insight(loc, collected, layer1_ctx, snap=peek_snapshot(loc))
                            follow2 = "Updated insight packet:\n" + insight_packet.model_dump_json() + "\nJSON InsightReply only."
                        else:
                            follow2 = f"data result:\n{json.dumps(pack['result'], ensure_ascii=False)[:8000]}\nNow answer in ordinary English."
                        messages.append(
                            {
                                "role": "user",
                                "content": follow2,
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
                                    "This question needs Prithvi AI figures. "
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
                        tool_out = pack["result"]
                    if insight_turn:
                        from app.agents.insight_compiler import compile_insight
                        from app.services.snapshot import peek_snapshot

                        insight_packet = compile_insight(loc, collected, layer1_ctx, snap=peek_snapshot(loc))
                        tool_blob = insight_packet.model_dump_json()
                    else:
                        tool_blob = json.dumps(tool_out, ensure_ascii=False)[:8000]
                    messages.append(
                        {
                            "role": "tool",
                            "tool_call_id": c.get("id") or "x",
                            "content": tool_blob,
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
                                f"Answer in 2–4 English sentences with 1 practical, actionable suggestion for the user ({domain}). "
                                "Quote only 1–3 figures from the data. No raw dumps."
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
            "message": f"Ollama not reachable ({ollama_msg}). Start `ollama serve` (qwen2.5:3b on 6 GB GPU).",
        }

    leaked = parse_text_call(english_llm or "")
    if leaked and leaked.get("need") and leaked["need"] not in collected:
        pack = await exec_data(leaked)
        yield pack["start"]
        yield {"type": "tool_result", "name": "data", "data": pack["result"], "ms": pack["ms"]}
        english_llm = ""
    english_llm = strip_tool_syntax(english_llm or "")
    if tri.kind == "chat" and not needed and parse_text_call(english_llm or ""):
        english_llm = ""
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
                                f"Answer the user in 2–4 sentences with 1 actionable recommendation ({domain}). "
                                "No digits unless they appear above. No JSON."
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

    cf_scale = detect_scale(message_en)
    if cf_scale and "forecast" in collected and isinstance(collected["forecast"], dict):
        collected["forecast"] = scale_forecast(collected["forecast"], cf_scale)
        collected["counterfactual"] = {
            "need": "counterfactual",
            "scale": cf_scale,
            "precip_next_3d_mm": collected["forecast"].get("precip_next_3d_mm"),
            "note": collected["forecast"].get("note"),
        }

    payloads = list(collected.values())
    if insight_turn:
        from app.agents.insight_compiler import compile_insight, finish_insight_body
        from app.services.snapshot import peek_snapshot

        if insight_packet is None:
            insight_packet = compile_insight(loc, collected, layer1_ctx, snap=peek_snapshot(loc))
        body, _src = finish_insight_body(english_llm, insight_packet, collected, message_en)
        payloads = list(collected.values()) + [{"cites": insight_packet.cites}]
        content_en, rejected = check_claims(body, payloads, window=window_hint)
        english_llm = body
    else:
        content_en, rejected = check_claims(english_llm, payloads, window=window_hint)
    asked_name = place or (prior.asked if prior and inherit else None) or loc.place_name or loc.district
    pin_from_client = pin_now.label
    content_en = strip_unasked_pin(content_en, place, pin_from_client)
    allowed = [loc.place_name, loc.district, loc.label, loc.state, asked_name, place]
    other = extract_compare_other(message_en, loc.place_name or loc.district)
    if other:
        allowed.append(other)
    for pack in collected.values():
        if not isinstance(pack, dict):
            continue
        for r in pack.get("ranked") or []:
            if isinstance(r, dict) and r.get("district"):
                allowed.append(str(r["district"]))
        if pack.get("state"):
            allowed.append(str(pack["state"]))
    forbidden = ["Patna", "Bihar"]
    if not any(_fold_hit("Haldia", n) for n in allowed if n):
        forbidden.append("Haldia")
    if not _same_pin(pin_now, loc):
        forbidden.append(pin_now.place_name or pin_now.district)
    if loc.state and loc.state.lower() == "bihar":
        forbidden = [f for f in forbidden if f.lower() not in {"patna", "bihar"}]
    content_en = strip_foreign_places(content_en, allowed, forbidden)
    content_en = fill_slots(content_en, collected)
    content_en = drop_false_shrug(content_en, collected)
    quoted = present_answer(collected, window=window_hint, compact=True, domain=domain, query=message_en, activity=activity)
    raw_ev = quote_facts(collected, window=window_hint)
    show_ev = bool(payload.show_evidence)
    llm_ok = bool(content_en) and not is_dash_soup(content_en) and not rejected
    if insight_turn:
        quoted = ""
        raw_ev = ""
    if quoted and needed:
        if not content_en or is_dash_soup(content_en) or rejected:
            content_en = quoted
        elif show_ev and raw_ev and raw_ev not in content_en:
            content_en = f"{content_en}\n\n---\nEvidence\n{raw_ev}".strip()
    elif quoted and (not content_en or is_dash_soup(content_en) or rejected):
        content_en = quoted
    if not content_en:
        if collected:
            content_en = quoted or "Here is what Prithvi AI has for that."
        else:
            content_en = (
                "I can chat about Indian weather, flood, heat, air, marine, and field decisions. "
                "What would you like to know?"
            )
    if beyond:
        content_en = f"{content_en}\n\n{BEYOND_SKILL}".strip() if content_en else BEYOND_SKILL
    if needed and not insight_turn:
        try:
            from app.rag.store import retrieve as rag_retrieve

            topic = (needed or ["forecast"])[0]
            guide = rag_retrieve(topic, "en")
            snippet = (guide.get("text") or "").strip().split("\n")[0]
            if snippet and not snippet.startswith("#") and len(snippet) < 220 and snippet not in (content_en or ""):
                content_en = f"{content_en}\n\n{snippet}".strip()
        except Exception:
            pass
    content_en = hedge(content_en, collected)
    content_en = severity(content_en, collected)
    led = ledger_for(collected)
    plan_id = f"{payload.conversation_id or 'anon'}:{uuid.uuid4().hex[:8]}"

    if rejected and rejected != ["dump"]:
        yield {"type": "notice", "message": f"Ungrounded figures replaced: {rejected[:8]}"}

    blocks = attachments_for(collected)
    suggestions = suggestions_for(collected, loc)
    if suggestions:
        yield {"type": "suggestions", "suggestions": suggestions}

    content, outbound, engine = await _localize_validated(content_en, out_locale, native=native_gemini)
    if not english_llm and engine == "llm-en":
        engine = "chat-fallback"
    if out_locale != "en" and content_en:
        if engine.startswith("llm-en+"):
            yield {"type": "notice", "message": f"Translated answer en → {out_locale} ({outbound.engine})."}
        else:
            yield {"type": "notice", "message": "Showing English (whole-document translation unavailable)."}

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
                else (
                    prior.asked
                    if prior and inherit
                    else (loc.place_name or loc.district if needed else None)
                )
            ),
            catalog=bool(plan.catalog or (prior.catalog if prior and inherit else False)),
            pin=pin_now.model_dump(),
            plan_id=plan_id,
            evidence_root=led.get("root"),
            window=window_hint,
            needs=list(needed or (prior.needs if prior and inherit else [])),
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
        "evidence_root": led.get("root"),
        "plan_id": plan_id,
        "triage": tri.kind,
        "insight": (
            {
                "sentiment": insight_packet.sentiment,
                "tone": insight_packet.tone,
                "bands": [b.model_dump() for b in insight_packet.bands if not b.missing],
                "packet_id": insight_packet.pack_fingerprint,
            }
            if insight_turn and payload.show_evidence and insight_packet is not None
            else None
        ),
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

"""Layer 1: Semantic Context, Intent & Entity Extractor (Hybrid).

Parses natural language queries to disentangle activities, geographical entities,
temporal horizons, and operational domains. Synthesizes a bespoke Layer 2 prompt.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any

from app.agents.dates import parse_window, today_ist
from app.agents.dimensions import detect_domain
from app.data.india_districts import match_state, match_states, state_representative_district
from app.schemas.location import Location

_ACTIVITY_WORDS: dict[str, str] = {
    "skydiving": "aviation",
    "skydive": "aviation",
    "paragliding": "aviation",
    "paraglide": "aviation",
    "flying": "aviation",
    "drone": "aviation",
    "uav": "aviation",
    "aviation": "aviation",
    "flight": "aviation",
    "crop spraying": "farming",
    "spraying": "farming",
    "spray": "farming",
    "irrigation": "farming",
    "irrigate": "farming",
    "sowing": "farming",
    "harvesting": "farming",
    "harvest": "farming",
    "farming": "farming",
    "flood monitoring": "disaster",
    "evacuation": "disaster",
    "rescue": "disaster",
    "boating": "marine",
    "fishing": "marine",
    "sailing": "marine",
    "swimming": "urban",
    "swim": "urban",
    "picnic": "urban",
    "hiking": "urban",
    "trekking": "urban",
    "cycling": "urban",
    "running": "urban",
    "jogging": "urban",
    "jog": "urban",
    "walking": "urban",
    "walk": "urban",
    "camping": "urban",
    "camp": "urban",
    "outdoor sports": "urban",
    "cricket": "urban",
    "commute": "urban",
    "driving": "urban",
    "finishing": "urban",
}


@dataclass
class SemanticContext:
    """Structured understanding of the user's turn produced by Layer 1."""

    query_en: str
    domain: str  # aviation | disaster | farming | marine | urban | general
    activity: str | None = None
    place_raw: str | None = None
    place_resolved: Location | None = None
    is_state: bool = False
    state_name: str | None = None
    time_window: dict[str, str] | None = None  # {start, end, hour}
    intent: str = "forecast"  # activity_feasibility | forecast | rain_window | nowcast | aqi | rank | chit_chat
    sentiment: str = "inquisitive"  # operational_safety | casual_planning | inquisitive | emergency
    tailored_system_prompt: str = ""
    tailored_user_hint: str = ""


def _extract_activity(text: str) -> tuple[str | None, str | None]:
    """Detect if an outdoor/operational activity is explicitly mentioned."""
    t = (text or "").lower()
    for act, dom in _ACTIVITY_WORDS.items():
        if re.search(rf"\b{re.escape(act)}\b", t):
            return act, dom
    return None, None


def _clean_location_candidate(raw: str | None) -> str | None:
    """Strip extraneous activity verbs, prepositions, and stop tokens from a place candidate."""
    if not raw:
        return None
    # Remove leading prepositions / pronouns
    cleaned = re.sub(r"^(?:in|at|near|around|for|to|of|the|my|our)\s+", "", raw.strip(), flags=re.I)
    # Remove trailing time words or punctuation
    cleaned = re.sub(
        r"\s+(?:today|tomorrow|tonight|now|this\s+week|next\s+week|please)[?.!,]*$",
        "",
        cleaned,
        flags=re.I,
    )
    cleaned = cleaned.strip(" ?,.!")
    # If the candidate contains an activity word, remove it
    for act in _ACTIVITY_WORDS:
        cleaned = re.sub(rf"\b{re.escape(act)}\b", "", cleaned, flags=re.I).strip()
    # Single gerund/verb ending in -ing is not a place (unless Darjeeling/Pelling)
    if cleaned.lower().endswith("ing") and cleaned.lower() not in {"darjeeling", "pelling"}:
        return None
    return cleaned if len(cleaned) >= 2 else None


def fast_parse_entities(text: str) -> tuple[str | None, str | None, str | None]:
    """Fast deterministic extractor separating activity from place entity."""
    raw = (text or "").strip()
    activity, dom = _extract_activity(raw)

    # 1. Check for spatial prepositions (in | at | near | around)
    m_loc = re.search(
        r"\b(?:in|at|near|around)\s+([A-Za-z][A-Za-z .'-]{1,40}?)"
        r"(?=\s*[?.!,;]|$|\s+(?:today|tomorrow|tonight|now|next|this|please|are|is|was|were|will|that|which|more|list|how|and|or)\b)",
        raw,
        re.I,
    )
    if m_loc:
        place_cand = _clean_location_candidate(m_loc.group(1))
        if place_cand:
            return activity, dom, place_cand

    # 2. Check for "for <place>" only if no spatial preposition exists and NOT preceded by "go for"
    m_for = re.search(
        r"\b(?:forecast|weather|rain|conditions|outlook)?\s*(?:for|of)\s+([A-Za-z][A-Za-z .'-]{1,40}?)"
        r"(?=\s*[?.!,;]|$|\s+(?:today|tomorrow|tonight|now|next|this|please|are|is|was|were|will|that|which|more|list|how|and|or)\b)",
        raw,
        re.I,
    )
    if m_for:
        prefix = raw[:m_for.start()].rstrip().lower()
        if not re.search(r"\b(?:go|going|head|headed|plan|planning|ready)\s*$", prefix):
            cand = _clean_location_candidate(m_for.group(1))
            if cand and not any(cand.lower() == a for a in _ACTIVITY_WORDS):
                return activity, dom, cand

    return activity, dom, None


async def parse_semantic_context(
    message_en: str,
    history_en: list[dict[str, Any]] | None = None,
    default_loc: Location | None = None,
    prior_window: dict[str, str] | None = None,
) -> SemanticContext:
    """Layer 1 Hybrid Parser: combines fast deterministic extraction with LLM fallback."""
    from app.agents.utterance import resolve_named_place
    from app.agents.dates import parse_window, today_ist

    text = (message_en or "").strip()
    history = history_en or []

    # 1. Detect activity & candidate place via fast path
    activity, act_domain, place_cand = fast_parse_entities(text)
    domain = act_domain or detect_domain(text, [h.get("content", "") for h in history])

    # 2. Resolve place
    resolved: Location | None = None
    is_state = False
    state_name: str | None = None

    # Check if a state is explicitly named in the text
    st_matches = match_states(text)
    if place_cand:
        resolved = resolve_named_place(place_cand)
        if not resolved and match_state(place_cand):
            st_name = match_state(place_cand)
            if st_name:
                is_state = True
                state_name = st_name
                hub_dict = state_representative_district(st_name)
                if hub_dict:
                    resolved = resolve_named_place(hub_dict.get("label") or hub_dict.get("district"))
    elif st_matches:
        is_state = True
        state_name = st_matches[0]
        hub_dict = state_representative_district(state_name)
        if hub_dict:
            resolved = resolve_named_place(hub_dict.get("label") or hub_dict.get("district"))

    # If place_cand exists but wasn't resolved, try resolving with gazetteer
    if place_cand and not resolved:
        resolved = resolve_named_place(place_cand)

    # 3. Resolve temporal window
    today = today_ist()
    win = parse_window(text, today)
    time_window: dict[str, str] | None = None
    if win:
        time_window = {
            "start": win["start"].isoformat(),
            "end": win["end"].isoformat(),
        }
    elif prior_window:
        time_window = dict(prior_window)

    # 4. Determine intent
    t_low = text.lower()
    if activity:
        intent = "activity_feasibility"
    elif any(w in t_low for w in ("rank", "ranking", "worst", "highest", "top")):
        intent = "rank"
    elif any(w in t_low for w in ("aqi", "pollution", "air quality", "pm2")):
        intent = "aqi"
    elif any(w in t_low for w in ("nowcast", "next hour", "0-6", "pump")):
        intent = "nowcast"
    else:
        intent = "forecast"

    # 5. Determine sentiment
    if domain in {"aviation", "disaster"}:
        sentiment = "operational_safety"
    elif activity:
        sentiment = "casual_planning"
    else:
        sentiment = "inquisitive"

    # 6. Synthesize Layer 2 Tailored Prompt & Hint
    place_label = resolved.label if resolved else (default_loc.label if default_loc else "this location")
    time_label = ""
    if time_window:
        if time_window.get("start") == time_window.get("end"):
            time_label = f"for {time_window.get('start')}"
        else:
            time_label = f"from {time_window.get('start')} to {time_window.get('end')}"

    tailored_hint = (
        f"LAYER 1 CONTEXT:\n"
        f"- Domain: {domain.upper()} (User role: {domain})\n"
        f"- Intent: {intent.replace('_', ' ').title()}\n"
        + (f"- Activity: {activity.upper()}\n" if activity else "")
        + (f"- Region/State: {state_name} (Representative Hub: {place_label})\n" if is_state else f"- Target Location: {place_label}\n")
        + (f"- Time Horizon: {time_label}\n" if time_label else "")
        + f"- Brevity Rule: 2 to 4 sentences maximum. Quote 1–3 figures.\n"
        + f"- Actionable Advice: Provide 1 practical recommendation specifically for {activity or domain}."
    )

    return SemanticContext(
        query_en=text,
        domain=domain,
        activity=activity,
        place_raw=place_cand,
        place_resolved=resolved,
        is_state=is_state,
        state_name=state_name,
        time_window=time_window,
        intent=intent,
        sentiment=sentiment,
        tailored_user_hint=tailored_hint,
    )

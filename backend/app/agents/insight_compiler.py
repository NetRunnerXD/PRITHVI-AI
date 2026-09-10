"""Deterministic Insight Packet: band labels before the LLM sees numbers."""

from __future__ import annotations

import hashlib
import re
from datetime import datetime, timezone
from typing import Any

from app.agents.views import compact_nowcast, strip_forbidden
from app.providers.datagov import aqi_category
from app.schemas.insight import Band, InsightPacket
from app.schemas.location import Location
from app.services.snapshot import pin_key

INSIGHT_L1 = frozenset({"forecast", "nowcast", "aqi", "activity_feasibility"})
INSIGHT_NEEDS = frozenset({"forecast", "nowcast", "rain_window", "aqi"})

EPA_AQI = (
    (50, "Good", "good"),
    (100, "Moderate", "moderate"),
    (150, "Unhealthy for Sensitive Groups", "usg"),
    (200, "Unhealthy", "unhealthy"),
    (300, "Very Unhealthy", "very_unhealthy"),
    (500, "Hazardous", "hazardous"),
)

CPCB_BAND = {
    "Good": "good",
    "Satisfactory": "satisfactory",
    "Moderate": "moderate",
    "Poor": "poor",
    "Very Poor": "very_poor",
    "Severe": "severe",
}

CPCB_MEANING = {
    "Good": "Air is fine for outdoor time.",
    "Satisfactory": "Air is acceptable for most people.",
    "Moderate": "Air is moderate; sensitive people should ease outdoor work.",
    "Poor": "Air is poor for outdoor work and children.",
    "Very Poor": "Air is very poor; keep children and outdoor labour inside.",
    "Severe": "Air is severe; avoid outdoor exposure.",
}


def us_epa_aqi_category(value: float) -> tuple[str, str]:
    for cap, label, band in EPA_AQI:
        if value <= cap:
            return label, band
    return "Hazardous", "hazardous"


def insight_eligible(layer1: Any, gate: Any, tri: Any, plan: Any) -> bool:
    kind = getattr(tri, "kind", None) or ""
    if kind in {"emergency", "refuse"}:
        return False
    if getattr(gate, "mode", None) == "refuse":
        return False
    needs = list(getattr(gate, "needs", None) or [])
    if kind == "chat" and not needs:
        return False
    if getattr(plan, "catalog", False):
        return False
    if any(n in needs for n in ("rank", "states_weather", "compare")):
        return False
    intent = getattr(layer1, "intent", None) or ""
    if intent in INSIGHT_L1:
        return True
    if needs and set(needs) <= (INSIGHT_NEEDS | {"warnings", "risks"}):
        if set(needs) & INSIGHT_NEEDS:
            return True
    return False


def insight_canary(conversation_id: str | None, percent: int, flag: bool) -> bool:
    if not flag or percent <= 0:
        return False
    cid = (conversation_id or "").strip()
    if percent >= 100:
        return True
    if not cid:
        return False
    n = int(hashlib.sha256(cid.encode("utf-8")).hexdigest(), 16) % 100
    return n < percent


def cache_key(loc: Location, generated_at: str, fingerprint: str) -> str:
    return f"insight:{pin_key(loc)}:{generated_at}:{fingerprint}"


def _num(v: Any) -> float | None:
    try:
        if v is None or v is False:
            return None
        return float(v)
    except (TypeError, ValueError):
        return None


def _cpcb_band(value: float) -> Band:
    cat = aqi_category(value)
    band = CPCB_BAND.get(cat, "severe")
    return Band(
        key="aqi_now",
        scale="cpcb",
        category=cat,
        band=band,
        significance=None,
        meaning=CPCB_MEANING.get(cat, "Air quality needs care."),
        raw_cite=f"cpcb={int(round(value))}",
        missing=False,
    )


def _epa_band(value: float, key: str = "aqi_now") -> Band:
    cat, band = us_epa_aqi_category(value)
    meaning = {
        "good": "US AQI is good.",
        "moderate": "US AQI is moderate.",
        "usg": "US AQI is unhealthy for sensitive groups.",
        "unhealthy": "US AQI is unhealthy.",
        "very_unhealthy": "US AQI is very unhealthy.",
        "hazardous": "US AQI is hazardous.",
    }.get(band, "US AQI needs care.")
    return Band(
        key=key,
        scale="us_epa",
        category=cat,
        band=band,
        meaning=meaning,
        raw_cite=f"us_aqi={int(round(value))}",
    )


def _delta_sig(delta: float) -> str:
    ad = abs(delta)
    if ad < 10:
        return "none"
    if ad < 25:
        return "low"
    if ad < 51:
        return "medium"
    return "significant"


def _rain_category(rate: float | None, prob: float | None) -> tuple[str, str, str]:
    """Return category, rate_band, likelihood."""
    rate_band = "missing"
    if rate is not None:
        if rate < 0.2:
            rate_band = "dry"
        elif rate < 1.0:
            rate_band = "light"
        elif rate < 4.0:
            rate_band = "moderate"
        else:
            rate_band = "heavy"
    likelihood = "ignore"
    if prob is not None:
        if prob < 30:
            likelihood = "unlikely"
        elif prob < 60:
            likelihood = "possible"
        else:
            likelihood = "likely"
    if rate is None and (prob is None or likelihood == "ignore"):
        return "missing", rate_band, likelihood
    if rate is not None and rate >= 4.0:
        cat = "heavy"
    elif (rate is not None and rate >= 1.0) or likelihood == "likely":
        cat = "likely"
    elif (rate is not None and rate >= 0.2) or likelihood == "possible":
        cat = "possible"
    else:
        cat = "unlikely"
    return cat, rate_band, likelihood


def _extract_rate_prob(collected: dict[str, Any], snap: Any | None) -> tuple[float | None, float | None]:
    rate = None
    prob = None
    nc = collected.get("nowcast") or {}
    if isinstance(nc, dict):
        locked = nc.get("nowcast") if isinstance(nc.get("nowcast"), dict) else nc.get("locked") or {}
        if isinstance(locked, dict):
            rate = _num(locked.get("mm_h") or locked.get("precip_1h_mm") or locked.get("rate_mm_h"))
        rate = rate if rate is not None else _num(nc.get("precip_1h_mm") or nc.get("mm_h"))
    fc = collected.get("forecast") or {}
    if isinstance(fc, dict):
        slot = fc.get("hourly_slot") if isinstance(fc.get("hourly_slot"), dict) else None
        if slot:
            if rate is None:
                rate = _num(slot.get("precip_mm"))
            if prob is None:
                prob = _num(slot.get("precip_prob_pct"))
        if rate is None:
            rate = _num(fc.get("precip_1h_mm"))
        hourly = fc.get("hourly") or fc.get("hours") or []
        probs: list[float] = []
        rates: list[float] = []
        if isinstance(hourly, list):
            for h in hourly[:2]:
                if not isinstance(h, dict):
                    continue
                p = _num(h.get("precipitation_probability") or h.get("precip_prob"))
                r = _num(h.get("precipitation") or h.get("precip_mm") or h.get("precip_1h_mm"))
                if p is not None:
                    probs.append(p)
                if r is not None:
                    rates.append(r)
        if probs:
            prob = max(probs)
        if rate is None and rates:
            rate = sum(rates) / max(len(rates), 1)
        if prob is None:
            pp = fc.get("precip_prob")
            if isinstance(pp, list) and pp:
                prob = _num(pp[0])
            else:
                prob = _num(fc.get("precip_probability"))
    if snap is not None:
        cur = getattr(getattr(snap, "descriptive", None), "current", None)
        if cur is not None and rate is None:
            rate = _num(getattr(cur, "precip_1h_mm", None))
        air = (getattr(snap, "quality", None) or {}).get("air") if snap else None
        if isinstance(air, dict) and prob is None:
            hp = air.get("hourly") or []
            if isinstance(hp, list):
                ps = [_num(h.get("precipitation_probability")) for h in hp[:2] if isinstance(h, dict)]
                ps = [p for p in ps if p is not None]
                if ps:
                    prob = max(ps)
    return rate, prob


def _aqi_from_collected(collected: dict[str, Any], snap: Any | None) -> tuple[Band | None, Band | None]:
    cpcb_val = None
    epa_val = None
    aqi = collected.get("aqi") or {}
    if isinstance(aqi, dict):
        cpcb = aqi.get("cpcb")
        if isinstance(cpcb, dict):
            cpcb_val = _num(cpcb.get("value"))
        epa_val = _num(aqi.get("om_us_aqi"))
    q = collected.get("quality") or {}
    if isinstance(q, dict):
        air = q.get("air") or {}
        if isinstance(air, dict) and epa_val is None:
            epa_val = _num(air.get("us_aqi") or air.get("om_us_aqi"))
    if snap is not None:
        cur = getattr(getattr(snap, "descriptive", None), "current", None)
        if cur is not None:
            if cpcb_val is None:
                cpcb_val = _num(getattr(cur, "aqi", None))
            if epa_val is None:
                epa_val = _num(getattr(cur, "om_us_aqi", None))
        air = (getattr(snap, "quality", None) or {})
        if isinstance(air, dict):
            a = air.get("air") or {}
            if isinstance(a, dict) and epa_val is None:
                epa_val = _num(a.get("us_aqi"))
    primary = None
    extra = None
    if cpcb_val is not None:
        primary = _cpcb_band(cpcb_val)
        if epa_val is not None:
            extra = _epa_band(epa_val, key="aqi_now_us")
    elif epa_val is not None:
        primary = _epa_band(epa_val, key="aqi_now")
    return primary, extra


def _aqi_delta(collected: dict[str, Any], snap: Any | None, scale: str | None) -> Band:
    now_v = None
    later = None
    src_scale = scale
    q = collected.get("quality") or {}
    air = q.get("air") if isinstance(q, dict) else {}
    if not isinstance(air, dict) and snap is not None:
        air = (getattr(snap, "quality", None) or {}).get("air") or {}
    if isinstance(air, dict):
        hourly = air.get("hourly") or air.get("us_aqi_hourly") or []
        if isinstance(hourly, list) and hourly:
            now_v = _num(hourly[0].get("us_aqi") if isinstance(hourly[0], dict) else None)
            if len(hourly) > 2:
                later = _num(hourly[2].get("us_aqi") if isinstance(hourly[2], dict) else None)
            elif len(hourly) > 1:
                later = _num(hourly[1].get("us_aqi") if isinstance(hourly[1], dict) else None)
        if now_v is None:
            now_v = _num(air.get("us_aqi"))
        src_scale = "us_epa"
    if now_v is None or later is None:
        return Band(
            key="aqi_delta_2h",
            scale=src_scale,
            category="missing",
            band="missing",
            significance=None,
            meaning="AQI two-hour change is not in this pack.",
            missing=True,
        )
    delta = later - now_v
    sig = _delta_sig(delta)
    if abs(delta) < 10:
        band = "steady"
    elif delta > 0:
        band = "increase"
    else:
        band = "decrease"
    return Band(
        key="aqi_delta_2h",
        scale="us_epa",
        category=band,
        band=band,
        significance=sig,
        meaning=f"AQI now vs two hours: {sig} {band}.",
        raw_cite=f"us_aqi_now={int(round(now_v))};us_aqi_2h={int(round(later))}",
    )


def _flood_band(collected: dict[str, Any], snap: Any | None) -> Band:
    score = None
    risks = collected.get("risks") or {}
    rows = risks.get("risks") if isinstance(risks, dict) else None
    if not rows and snap is not None:
        rows = [r.model_dump() if hasattr(r, "model_dump") else r for r in (getattr(snap, "risks", None) or [])]
    if isinstance(rows, list):
        for r in rows:
            if isinstance(r, dict) and r.get("id") == "flood":
                score = _num(r.get("score_pct"))
                break
    if score is None:
        return Band(
            key="flood",
            scale="score_pct",
            category="missing",
            band="missing",
            meaning="Flood score is not in this pack.",
            missing=True,
        )
    if score < 40:
        cat, band, meaning = "watch", "watch", "Flood score is in the watch band."
    elif score < 70:
        cat, band, meaning = "elevate", "elevate", "Flood score is elevated."
    else:
        cat, band, meaning = "danger", "danger", "Flood score is in the danger band."
    return Band(
        key="flood",
        scale="score_pct",
        category=cat,
        band=band,
        meaning=meaning,
        raw_cite=f"flood_score_pct={int(round(score))}",
    )


def _heat_band(collected: dict[str, Any], snap: Any | None) -> Band:
    wbgt = None
    level = None
    for pack in (collected.get("risks"), collected.get("forecast"), collected.get("nowcast")):
        if isinstance(pack, dict):
            w = pack.get("wbgt") or pack.get("science_wbgt")
            if isinstance(w, dict):
                wbgt = _num(w.get("wbgt_c"))
                level = w.get("level")
    if snap is not None and wbgt is None:
        sci = getattr(snap, "science", None) or {}
        w = sci.get("wbgt") if isinstance(sci, dict) else None
        if isinstance(w, dict):
            wbgt = _num(w.get("wbgt_c"))
            level = w.get("level")
    if wbgt is not None:
        lvl = str(level or "")
        if not lvl:
            if wbgt >= 32:
                lvl = "stop"
            elif wbgt >= 28:
                lvl = "limit"
            elif wbgt >= 26:
                lvl = "caution"
            else:
                lvl = "ok"
        meaning = {
            "ok": "Heat stress is low.",
            "caution": "Heat is in the caution band.",
            "limit": "Heat is in the limit band — slow outdoor work.",
            "stop": "Heat is in the stop band — avoid heavy outdoor labour.",
        }.get(lvl, "Heat needs care.")
        cat = "danger" if lvl in {"stop", "limit"} else ("caution" if lvl == "caution" else "ok")
        return Band(
            key="heat",
            scale="wbgt_c",
            category=cat,
            band=lvl,
            meaning=meaning,
            raw_cite=f"wbgt_c={wbgt:g}",
        )
    score = None
    rows = (collected.get("risks") or {}).get("risks") if isinstance(collected.get("risks"), dict) else None
    if not rows and snap is not None:
        rows = [r.model_dump() if hasattr(r, "model_dump") else r for r in (getattr(snap, "risks", None) or [])]
    if isinstance(rows, list):
        for r in rows:
            if isinstance(r, dict) and r.get("id") == "heat":
                score = _num(r.get("score_pct"))
                break
    if score is None:
        return Band(
            key="heat",
            scale="score_pct",
            category="missing",
            band="missing",
            meaning="Heat score is not in this pack.",
            missing=True,
        )
    if score < 40:
        cat, band, meaning = "ok", "ok", "Heat score is low."
    elif score < 70:
        cat, band, meaning = "caution", "caution", "Heat is in the caution band."
    else:
        cat, band, meaning = "danger", "danger", "Heat is in the danger band."
    return Band(
        key="heat",
        scale="score_pct",
        category=cat,
        band=band,
        meaning=meaning,
        raw_cite=f"heat_score_pct={int(round(score))}",
    )


def _actions(collected: dict[str, Any], snap: Any | None) -> list[str]:
    out: list[str] = []
    nc = collected.get("nowcast") or {}
    acts = nc.get("actions") if isinstance(nc, dict) else None
    if isinstance(acts, list):
        for a in acts:
            if isinstance(a, str) and a.strip():
                out.append(a.strip())
            elif isinstance(a, dict) and a.get("action"):
                out.append(str(a["action"]).strip())
    if snap is not None:
        pres = getattr(snap, "prescriptive", None)
        if pres is not None:
            for a in getattr(pres, "actions", None) or []:
                txt = getattr(a, "action", None) or (a.get("action") if isinstance(a, dict) else None)
                if txt:
                    out.append(str(txt).strip())
    fc = collected.get("forecast") or {}
    if isinstance(fc, dict) and not out:
        try:
            from app.ml.prescribe import recommend
            from app.schemas.risk import RiskCard

            risks_raw = (collected.get("risks") or {}).get("risks") or []
            cards = []
            for r in risks_raw:
                if isinstance(r, dict) and r.get("id"):
                    try:
                        cards.append(RiskCard.model_validate(r))
                    except Exception:
                        pass
            recs = recommend(
                {
                    "precip_3d_mm": fc.get("precip_next_3d_mm") or 0,
                    "precip_prob": fc.get("precip_prob") or [],
                    "soil_m3m3": fc.get("soil_m3m3") or 0.25,
                },
                cards,
            )
            for p in recs[:2]:
                if getattr(p, "action", None):
                    out.append(p.action)
        except Exception:
            pass
    # Unique, max 2, never DANGER_* protocol strings
    seen: list[str] = []
    for a in out:
        if "canned protocol" in a.lower():
            continue
        if a not in seen:
            seen.append(a)
        if len(seen) >= 2:
            break
    return seen


def snapshot_to_collected(snap: Any) -> dict[str, Any]:
    if snap is None:
        return {}
    cur = getattr(getattr(snap, "descriptive", None), "current", None)
    nc = (getattr(snap, "science", None) or {}).get("nowcast") if isinstance(getattr(snap, "science", None), dict) else {}
    collected: dict[str, Any] = {}
    if cur is not None:
        collected["aqi"] = {
            "need": "aqi",
            "cpcb": {"value": getattr(cur, "aqi", None)} if getattr(cur, "aqi", None) is not None else None,
            "om_us_aqi": getattr(cur, "om_us_aqi", None),
        }
        collected["forecast"] = {
            "need": "forecast",
            "precip_1h_mm": getattr(cur, "precip_1h_mm", None),
            "temp_c": getattr(cur, "temp_c", None),
        }
    if nc:
        collected["nowcast"] = compact_nowcast(nc) if isinstance(nc, dict) else {"nowcast": nc}
    risks = getattr(snap, "risks", None) or []
    collected["risks"] = {
        "need": "risks",
        "risks": [r.model_dump() if hasattr(r, "model_dump") else r for r in risks],
    }
    q = getattr(snap, "quality", None) or {}
    if q:
        collected["quality"] = {"need": "quality", **(q if isinstance(q, dict) else {})}
    return strip_forbidden(collected)


def compile_insight(
    loc: Location,
    collected: dict[str, Any],
    layer1: Any | None = None,
    snap: Any | None = None,
    generated_at: str | None = None,
) -> InsightPacket:
    collected = strip_forbidden(collected or {})
    ts = generated_at or (getattr(snap, "generated_at", None) if snap is not None else None)
    ts = ts or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    packs = sorted(k for k, v in collected.items() if v)
    fingerprint = hashlib.sha1(
        "|".join(packs + [getattr(layer1, "intent", "") or "forecast", ts]).encode()
    ).hexdigest()[:16]

    bands: list[Band] = []
    unknowns: list[str] = []
    needs_extra: list[str] = []

    aqi_now, aqi_us = _aqi_from_collected(collected, snap)
    if aqi_now:
        bands.append(aqi_now)
        if aqi_us:
            bands.append(aqi_us)
        bands.append(_aqi_delta(collected, snap, aqi_now.scale))
    else:
        unknowns.append("aqi_now")
        if "aqi" not in collected:
            needs_extra.append("aqi")

    rate, prob = _extract_rate_prob(collected, snap)
    cat, rate_band, likelihood = _rain_category(rate, prob)
    if cat == "missing":
        bands.append(
            Band(
                key="rain_next_2h",
                scale="mm_h",
                category="missing",
                band="missing",
                meaning="Rain in the next two hours is not in this pack.",
                missing=True,
            )
        )
        unknowns.append("rain_next_2h")
        if "nowcast" not in collected and "forecast" not in collected:
            needs_extra.append("nowcast")
    else:
        cites = []
        if rate is not None:
            cites.append(f"mm_h={rate:g}")
        if prob is not None:
            cites.append(f"prob={int(round(prob))}")
        meaning = {
            "heavy": "Heavy rain is likely here in the next two hours.",
            "likely": "Rain is likely here in the next two hours.",
            "possible": "Rain is possible here in the next two hours.",
            "unlikely": "Rain in the next two hours is unlikely.",
        }[cat]
        bands.append(
            Band(
                key="rain_next_2h",
                scale="mm_h" if rate is not None else "prob_pct",
                category=cat,
                band=cat,
                meaning=meaning,
                raw_cite=";".join(cites) or None,
            )
        )
        why = "model rate above dry threshold at this pin."
        nc = collected.get("nowcast") or {}
        conv = nc.get("convective") if isinstance(nc, dict) else None
        if conv:
            why = "convective signal plus rate above the dry threshold at this pin."
        if cat != "unlikely" or (rate is not None and rate >= 0.2):
            bands.append(
                Band(
                    key="rain_why",
                    scale=None,
                    category=cat,
                    band="why",
                    meaning=f"Rainfall at this time and place can happen because {why}",
                )
            )

    bands.append(_flood_band(collected, snap))
    if bands[-1].missing and "risks" not in collected:
        needs_extra.append("risks")
    bands.append(_heat_band(collected, snap))

    ranked = [b for b in bands if not b.missing] + [b for b in bands if b.missing]
    ranked = ranked[:8]
    actions = _actions(collected, snap)
    cites = [b.raw_cite for b in ranked if b.raw_cite]

    return InsightPacket(
        locus=loc.label or loc.district or loc.place_name or "",
        generated_at=ts,
        pack_fingerprint=fingerprint,
        sentiment=getattr(layer1, "sentiment", None) or "inquisitive",
        tone=getattr(layer1, "tone", None) or "curious",
        domain=getattr(layer1, "domain", None) or "general",
        intent=getattr(layer1, "intent", None) or "forecast",
        bands=ranked,
        actions=actions,
        unknowns=unknowns,
        cites=cites,
        needs_extra=list(dict.fromkeys(needs_extra)),
        playbook=None,
    )


_SENT_SPLIT = re.compile(r"(?<=[.!?])\s+")


def length_body(text: str, max_chars: int = 420, max_sents: int = 3) -> str:
    t = (text or "").strip()
    if not t:
        return t
    parts = [p.strip() for p in _SENT_SPLIT.split(t) if p.strip()]
    parts = parts[:max_sents]
    out = " ".join(parts)
    if len(out) <= max_chars:
        return out
    cut = out[:max_chars]
    sp = cut.rfind(" ")
    if sp > 40:
        cut = cut[:sp]
    return cut.rstrip(" ,;:") + ("." if not cut.endswith((".", "!", "?")) else "")


def parse_insight_reply(raw: str) -> dict[str, Any] | None:
    text = (raw or "").strip()
    if not text:
        return None
    candidates = [text]
    fence = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.S)
    if fence:
        candidates.insert(0, fence.group(1))
    brace = re.search(r"\{.*\}", text, re.S)
    if brace:
        candidates.append(brace.group(0))
    import json

    for c in candidates:
        try:
            obj = json.loads(c)
        except Exception:
            continue
        if isinstance(obj, dict) and ("meaning" in obj or "suggestion" in obj):
            return obj
    return None


def strip_ungrounded_text(text: str, allowed: set[str]) -> str:
    from app.i18n.number_lock import NUM, ungrounded

    bad = set(ungrounded(text, allowed))
    if not bad:
        return text

    def repl(m: re.Match[str]) -> str:
        tok = m.group(0)
        return "" if tok in bad else tok

    cleaned = NUM.sub(repl, text)
    cleaned = re.sub(r"\s{2,}", " ", cleaned).strip(" ,;:-")
    return cleaned


def template_from_packet(packet: InsightPacket, collected: dict[str, Any], query: str) -> str:
    from app.agents.facts import present_answer

    bits = []
    live = [b for b in packet.bands if not b.missing]
    if live:
        bits.append(live[0].meaning)
        if len(live) > 1:
            bits.append(live[1].meaning)
    if packet.actions:
        bits.append(packet.actions[0])
    body = " ".join(bits).strip()
    if body:
        return length_body(body)
    quoted = present_answer(collected, compact=True, query=query, domain=packet.domain)
    return length_body(quoted or "Rituchakra has no compiled insight for that yet.")


def finish_insight_body(
    raw_llm: str,
    packet: InsightPacket,
    collected: dict[str, Any],
    query: str,
) -> tuple[str, str]:
    """Return (body, source) where source is json|template."""
    from app.agents.binder import looks_like_dump
    from app.agents.facts import is_dash_soup
    from app.i18n.number_lock import allowed_from_tools

    parsed = parse_insight_reply(raw_llm)
    if not parsed:
        return template_from_packet(packet, collected, query), "template"
    meaning = str(parsed.get("meaning") or "").strip()
    suggestion = str(parsed.get("suggestion") or "").strip()
    extra = str(parsed.get("extra") or "").strip() or None
    body = " ".join(x for x in (meaning, suggestion, extra) if x)
    payloads = list(collected.values()) + [{"cites": packet.cites, "raw": [b.raw_cite for b in packet.bands]}]
    allowed = allowed_from_tools(payloads)
    body = strip_ungrounded_text(body, allowed)
    if not body.strip():
        return template_from_packet(packet, collected, query), "template"
    body = length_body(body)
    if looks_like_dump(body) or is_dash_soup(body):
        return template_from_packet(packet, collected, query), "template"
    return body, "json"

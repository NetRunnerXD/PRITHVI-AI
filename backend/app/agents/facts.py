"""When a question needs a figure, what we must refuse, and how to quote tool JSON."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import re

from app.agents.utterance import interpret, looks_like_bare_place  # noqa: F401
from app.i18n.number_lock import NUM

_PUSHBACK = (
    "still tell", "just tell", "tell me anyway", "tell me still",
    "i don't care", "i do not care", "go on", "anyway", "please just",
)


@dataclass
class Gate:
    """Source-gated plan: chat, fetch Rituchakra needs, or refuse unsourced metrics."""

    mode: str  # chat | data | refuse
    needs: list[str] = field(default_factory=list)
    states: list[str] = field(default_factory=list)
    refuse: str | None = None


def source_gate(text: str) -> Gate:
    """Refuse metrics Rituchakra does not compute. Fetch only named product needs."""
    plan = interpret(text)
    return Gate(mode=plan.mode, needs=list(plan.needs), states=list(plan.states), refuse=plan.refuse)


def is_pushback(text: str) -> bool:
    t = (text or "").lower()
    return any(p in t for p in _PUSHBACK) or (
        len(t.split()) <= 5 and any(w in t for w in ("still", "anyway", "please", "just tell"))
    )


_FALSE_SHRUG = re.compile(
    r"(couldn['’]?t find|could not find|no specific (weather|data|aqi|flood)|"
    r"don['’]?t have (any )?(specific )?(weather|data)|"
    r"no (weather|aqi|flood) data|not (able to )?find any)",
    re.I,
)


_SLOT = re.compile(r"\[([A-Za-z][A-Za-z0-9_]*)\]")

_SLOT_FROM = {
    "temp_c": ("temp_c",),
    "temp": ("temp_c",),
    "temperature": ("temp_c",),
    "rain_mm": ("precip_1h_mm", "precip_next_3d_mm", "total_mm"),
    "rain": ("precip_1h_mm", "precip_next_3d_mm", "total_mm"),
    "precip_mm": ("precip_1h_mm", "precip_next_3d_mm", "total_mm"),
    "precip_1h_mm": ("precip_1h_mm",),
    "precip_next_3d_mm": ("precip_next_3d_mm",),
    "precip_7d_mm": ("precip_7d_mm",),
    "aqi": ("value", "om_us_aqi"),
    "sky": ("sky_label",),
    "sky_label": ("sky_label",),
}


def _slot_catalog(collected: dict) -> dict[str, str]:
    """Flatten this-turn payloads into [slot] replacements."""
    flat: dict[str, Any] = {}

    def walk(obj: Any) -> None:
        if isinstance(obj, dict):
            for k, v in obj.items():
                if isinstance(v, (int, float)) and not isinstance(v, bool):
                    flat.setdefault(str(k).lower(), v)
                elif isinstance(v, str) and k.lower() in {"sky_label", "category", "label"}:
                    flat.setdefault(str(k).lower(), v)
                else:
                    walk(v)
        elif isinstance(obj, list):
            for x in obj[:8]:
                walk(x)

    walk(collected)
    out: dict[str, str] = {}
    for slot, keys in _SLOT_FROM.items():
        for k in keys:
            if k in flat and flat[k] is not None:
                v = flat[k]
                out[slot] = f"{v:g}" if isinstance(v, float) else str(v)
                break
    return out


def fill_slots(text: str, collected: dict) -> str:
    """Replace [temp_c] / [rain_mm] from fetched facts. Never leave a template token."""
    if not text:
        return text
    catalog = _slot_catalog(collected or {})

    def repl(m: re.Match[str]) -> str:
        key = m.group(1).lower()
        if key in catalog:
            return catalog[key]
        return "—"

    return _SLOT.sub(repl, text)


def is_dash_soup(text: str) -> bool:
    """True when claim-check turned a hallucinated outlook into 'August — / —%'."""
    raw = text or ""
    if raw.count("—") < 4:
        return False
    digits = NUM.findall(raw)
    return len(digits) <= 2


def drop_false_shrug(text: str, collected: dict) -> str:
    """If we already fetched figures, drop 'I couldn't find any weather' waffle."""
    if not text or not collected:
        return text
    if not _FALSE_SHRUG.search(text):
        return text
    keep = []
    for sent in re.split(r"(?<=[.!?])\s+", text):
        if _FALSE_SHRUG.search(sent):
            continue
        keep.append(sent)
    return " ".join(keep).strip()


def strip_unasked_pin(text: str, asked: str | None, pin_label: str | None) -> str:
    """Drop sentences that name the dashboard pin when the user asked about another place."""
    if not text or not asked or not pin_label:
        return text
    pin = pin_label.split(",")[0].strip().lower()
    ask = asked.lower()
    if pin in ask or pin == ask:
        return text
    keep = []
    for sent in re.split(r"(?<=[.!?])\s+", text):
        if pin in sent.lower() and ask not in sent.lower():
            continue
        keep.append(sent)
    return " ".join(keep).strip() or text


def strip_foreign_places(
    text: str,
    allowed: list[str] | None,
    forbidden: list[str] | None = None,
) -> str:
    """Drop sentences that name a town that is not the locus (or an explicit extra)."""
    if not text:
        return text
    allow = {n.split(",")[0].strip().lower() for n in (allowed or []) if n}
    forbid = {n.split(",")[0].strip().lower() for n in (forbidden or []) if n}
    forbid -= {a for a in allow if a}
    if not forbid:
        return text
    keep = []
    for sent in re.split(r"(?<=[.!?])\s+", text):
        low = sent.lower()
        if any(f in low for f in forbid) and not any(a and a in low for a in allow):
            continue
        keep.append(sent)
    return " ".join(keep).strip()


def needed_facts(text: str) -> list[str]:
    return source_gate(text).needs


def rank_metric(text: str) -> str:
    t = (text or "").lower()
    if any(w in t for w in ("driest", "drought", "dry")):
        return "drought"
    if any(w in t for w in ("heat", "hottest", "heatwave")):
        return "heat"
    if any(w in t for w in ("rain", "wettest", "precip")):
        return "rain"
    return "flood"


def _fmt(v: Any) -> str:
    if isinstance(v, float):
        return f"{v:g}"
    return str(v)


def quote_facts(collected: dict[str, Any]) -> str:
    """Deterministic lines from this turn's data() payloads. Never invent missing AQI as 0."""
    lines: list[str] = []
    win = collected.get("rain_window") or {}
    if isinstance(win, dict) and (win.get("days") or win.get("total_mm") is not None):
        loc = win.get("location") or {}
        name = loc.get("place_name") or loc.get("district") or loc.get("label") or "this place"
        start, end = win.get("start"), win.get("end")
        total = win.get("total_mm")
        lines.append(
            f"{name} {start} to {end}: {_fmt(total)} mm total (Open-Meteo daily, not a gauge)."
        )
        for row in (win.get("days") or [])[:8]:
            if not isinstance(row, dict):
                continue
            bit = f"{row.get('date')}: {_fmt(row.get('precip_mm'))} mm"
            if row.get("precip_prob_pct") is not None:
                bit += f" ({row.get('precip_prob_pct')}%)"
            lines.append(bit)
        missing = win.get("missing") or []
        if missing:
            lines.append("Not in the model horizon: " + ", ".join(str(m) for m in missing) + ".")
    nc = collected.get("nowcast") or {}
    locked = (nc.get("nowcast") if isinstance(nc, dict) else None) or {}
    pump = (nc.get("pump") if isinstance(nc, dict) else None) or {}
    if locked or pump:
        p = locked.get("p_interrupt_90m")
        if p is None:
            p = pump.get("p_interrupt_90m")
        onset = locked.get("onset")
        enter = locked.get("enterable_2h")
        where = nc.get("place") or ""
        bits = [f"{where} 0–6 h nowcast (locked):".strip() if where else "0–6 h nowcast (locked):"]
        if p is not None:
            bits.append(f"90 min interrupt {_fmt(p)}")
        if onset:
            bits.append(f"onset {onset}")
        if enter is not None:
            bits.append("field open" if enter else "field closed")
        lines.append("; ".join(bits) + ".")
    fc = collected.get("forecast") or {}
    if isinstance(fc, dict) and fc:
        place = fc.get("label") or fc.get("place") or ""
        now_bits = []
        if fc.get("sky_label"):
            now_bits.append(str(fc["sky_label"]))
        if fc.get("temp_c") is not None:
            now_bits.append(f"{_fmt(fc['temp_c'])}°C")
        if fc.get("precip_1h_mm") is not None:
            now_bits.append(f"this hour {_fmt(fc['precip_1h_mm'])} mm")
        if now_bits:
            lines.append(f"{place} now: " + ", ".join(now_bits) + " (Open-Meteo).")
        if fc.get("precip_next_3d_mm") is not None:
            lines.append(
                f"{place} next 3 days {_fmt(fc.get('precip_next_3d_mm'))} mm, "
                f"7 days {_fmt(fc.get('precip_7d_mm'))} mm."
            )
        for row in (fc.get("outlook_days") or [])[:7]:
            if not isinstance(row, dict):
                continue
            day = row.get("date")
            if not day:
                continue
            bit = f"{day}"
            if row.get("temp_max_c") is not None:
                bit += f" tmax {_fmt(row.get('temp_max_c'))}°C"
            if row.get("temp_min_c") is not None:
                bit += f" / {_fmt(row.get('temp_min_c'))}°C"
            if row.get("precip_mm") is not None:
                bit += f", {_fmt(row.get('precip_mm'))} mm"
            if row.get("precip_prob_pct") is not None:
                bit += f" ({row.get('precip_prob_pct')}%)"
            lines.append(bit + ".")
    aqi = collected.get("aqi")
    if isinstance(aqi, dict) and aqi:
        cpcb = aqi.get("cpcb") or {}
        st = aqi.get("provider_status") or ""
        val = cpcb.get("value") if isinstance(cpcb, dict) else None
        if st in {"ok", ""} and isinstance(val, (int, float)) and not (
            val == 0 and not cpcb.get("pollutants")
        ):
            local = cpcb.get("is_local_station")
            where = cpcb.get("station") or cpcb.get("city") or ""
            extra = "" if local else " (nearest CPCB city, not the asked town)"
            lines.append(
                f"CPCB AQI {_fmt(val)} ({cpcb.get('category') or ''}) at {where}{extra}.".replace(" ()", "")
            )
        elif aqi.get("om_us_aqi") is not None:
            lines.append(
                f"No CPCB station reading for {aqi.get('place') or 'this place'}. "
                f"Open-Meteo US AQI {_fmt(aqi.get('om_us_aqi'))} (model, not CPCB)."
            )
        else:
            reason = aqi.get("note") or st or "empty"
            lines.append(
                f"Rituchakra has no AQI for {aqi.get('place') or 'this place'} ({reason}). "
                "I will not invent 0."
            )
    cmp = collected.get("compare") or {}
    delta = (cmp.get("delta_a_minus_b") if isinstance(cmp, dict) else None) or {}
    if delta.get("rain_3d_mm") is not None:
        lines.append(f"Compare 3-day rain delta {_fmt(delta.get('rain_3d_mm'))} mm.")
    for key, rank in collected.items():
        if not (key == "rank" or str(key).startswith("rank:")):
            continue
        if not isinstance(rank, dict):
            continue
        ranked = rank.get("ranked")
        if not ranked:
            continue
        top = ranked[0]
        lines.append(
            f"{rank.get('state')} {rank.get('metric')} rank 1: {top.get('district')} "
            f"score {_fmt(top.get('flood_score'))}, 3d rain {_fmt(top.get('precip_3d_mm'))} mm."
        )
        for i, r in enumerate(ranked[1:6], 2):
            lines.append(
                f"{i}. {r.get('district')} flood {_fmt(r.get('flood_score'))}, "
                f"{_fmt(r.get('precip_3d_mm'))} mm / 3d"
            )
    sw = collected.get("states_weather") or {}
    srows = sw.get("ranked") if isinstance(sw, dict) else None
    if srows:
        lines.append(
            f"India state HQ ranking by {sw.get('metric')} "
            f"({sw.get('note') or 'weather/flood, not tourism'}):"
        )
        for i, r in enumerate(srows[:8], 1):
            lines.append(
                f"{i}. {r.get('state')} ({r.get('district')} HQ): flood {_fmt(r.get('flood_score'))}, "
                f"3d rain {_fmt(r.get('precip_3d_mm'))} mm, tmax {_fmt(r.get('temp_max_c'))}°C"
            )
    risks = collected.get("risks") or {}
    cards = risks.get("risks") if isinstance(risks, dict) else None
    if cards:
        for c in cards:
            if isinstance(c, dict) and c.get("score_pct") is not None:
                lines.append(f"{c.get('label') or c.get('id')} {c.get('score_pct')}% ({c.get('severity')}).")
    warns = collected.get("warnings")
    wrows = warns.get("warnings") if isinstance(warns, dict) else None
    if wrows:
        titles = [str(w.get("title")) for w in wrows[:3] if isinstance(w, dict) and w.get("title")]
        if titles:
            lines.append("Watches: " + "; ".join(titles) + ".")
        else:
            lines.append("No district CAP titles in the current Rituchakra watch list.")
    cap = collected.get("capability") or {}
    if isinstance(cap, dict) and cap.get("available") is False and cap.get("reason"):
        lines.append(str(cap["reason"]))
    elif isinstance(cap, dict) and cap.get("unavailable"):
        holes = cap["unavailable"]
        if isinstance(holes, dict) and holes:
            lines.append("Not ingested here: " + "; ".join(str(v) for v in list(holes.values())[:5]))
    mandi = collected.get("mandi") or {}
    rows = mandi.get("mandi") if isinstance(mandi, dict) else None
    if isinstance(mandi, dict) and mandi.get("need") == "mandi":
        if rows:
            bits = []
            for r in rows[:5]:
                if isinstance(r, dict) and r.get("modal_price") is not None:
                    bits.append(f"{r.get('commodity')} {_fmt(r.get('modal_price'))} INR/qtl")
            if bits:
                lines.append("Mandi: " + "; ".join(bits) + ".")
        else:
            lines.append(f"No Agmarknet arrivals in Rituchakra for {mandi.get('place') or 'this district'} today.")
    return "\n".join(lines).strip()


def prose_has_payload_number(text: str, collected: dict[str, Any]) -> bool:
    blob = text or ""
    found = set(NUM.findall(blob))
    if not found:
        return False
    skip = {str(i) for i in range(0, 16)} | {"2024", "2025", "2026", "2027", "2028"}
    for pack in collected.values():
        if not isinstance(pack, dict):
            continue
        stack = [pack]
        while stack:
            cur = stack.pop()
            if isinstance(cur, dict):
                stack.extend(cur.values())
            elif isinstance(cur, list):
                stack.extend(cur)
            elif isinstance(cur, (int, float)) and not isinstance(cur, bool):
                for form in (str(cur), f"{cur:g}"):
                    if form in found and form not in skip:
                        return True
    return False

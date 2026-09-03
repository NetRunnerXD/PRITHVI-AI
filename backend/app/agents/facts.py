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


_NULL_METRIC = re.compile(
    r"(?:—|–|\bnull\b|\bnone\b)\s*(?:°\s*C|°C|mm|%|hPa|m/s|मिमी|মিমি|लीटर|লিটার)|"
    r"(?:AQI|°C|mm|मिमी|মিমি)\s*[:\s]*(?:—|–|\bnull\b)",
    re.I,
)


def has_null_metrics(text: str) -> bool:
    """True when millimetres / °C / AQI were replaced by an em dash or null."""
    raw = text or ""
    if raw.count("—") >= 3 and len(NUM.findall(raw)) <= 1:
        return True
    return bool(_NULL_METRIC.search(raw))


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
    from app.agents.dimensions import mentioned_places
    from app.data.india_districts import match_states

    allow = {n.split(",")[0].strip().lower() for n in (allowed or []) if n}
    forbid = {n.split(",")[0].strip().lower() for n in (forbidden or []) if n}
    for p in mentioned_places(text):
        key = p.split(",")[0].strip().lower()
        if key and key not in allow:
            forbid.add(key)
    home_states = set()
    for n in allowed or []:
        blob = (n or "").lower()
        for st in match_states(n or ""):
            home_states.add(st.lower())
        if "west bengal" in blob or "bengal" in blob:
            home_states.add("west bengal")
    forbid -= {a for a in allow if a}
    if not forbid and not home_states:
        return text
    keep = []
    for sent in re.split(r"(?<=[.!?।])\s+", text):
        low = sent.lower()
        if any(len(f) >= 4 and f in low for f in forbid) and not any(a and len(a) >= 3 and a in low for a in allow):
            continue
        foreign_st = [s for s in match_states(sent) if s.lower() not in home_states]
        if foreign_st and home_states and not any(a and a in low for a in allow):
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
    if v is None:
        return "not reported"
    if isinstance(v, float):
        return f"{v:g}"
    return str(v)


def quote_facts(collected: dict[str, Any], window: dict[str, str] | None = None) -> str:
    """Deterministic lines from this turn's data() payloads. Never invent missing AQI as 0."""
    lines: list[str] = []
    wstart = str((window or {}).get("start") or "")[:10]
    wend = str((window or {}).get("end") or "")[:10]
    win = collected.get("rain_window") or {}
    has_rain_days = isinstance(win, dict) and bool(win.get("days") or win.get("total_mm") is not None)
    single_day = bool(wstart and wend and wstart == wend and has_rain_days)
    if isinstance(win, dict) and (win.get("days") or win.get("total_mm") is not None):
        loc = win.get("location") or {}
        name = loc.get("place_name") or loc.get("district") or loc.get("label") or "this place"
        start, end = win.get("start"), win.get("end")
        days = [r for r in (win.get("days") or []) if isinstance(r, dict)]
        if single_day:
            days = [r for r in days if str(r.get("date") or "")[:10] == wstart] or days
            known = [float(r["precip_mm"]) for r in days if r.get("precip_mm") is not None]
            total = sum(known) if known else None
            clock = (window or {}).get("hour")
            clock_bit = f" (asked hour {clock}:00 IST; model is daily, not a {clock}:00 gauge)" if clock not in (None, "") else ""
            lines.append(
                f"{name} {wstart}: {_fmt(total)} mm (Open-Meteo daily, not a gauge).{clock_bit}"
            )
        else:
            total = win.get("total_mm")
            lines.append(
                f"{name} {start} to {end}: {_fmt(total)} mm total (Open-Meteo daily, not a gauge)."
            )
        for row in days[:8]:
            bit = f"{row.get('date')}: rain {_fmt(row.get('precip_mm'))} mm"
            if row.get("precip_prob_pct") is not None:
                bit += f" ({row.get('precip_prob_pct')}%)"
            if row.get("sky_label"):
                bit += f", {row.get('sky_label')}"
            if row.get("temp_max_c") is not None:
                bit += f", tmax {_fmt(row.get('temp_max_c'))}°C"
            if row.get("wind_speed_max_kmh") is not None:
                bit += f", wind max {_fmt(row.get('wind_speed_max_kmh'))} km/h"
            else:
                bit += ", wind not reported"
            if row.get("wind_gust_max_kmh") is not None:
                bit += f", gust {_fmt(row.get('wind_gust_max_kmh'))} km/h"
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
        if not single_day and not (isinstance(win, dict) and win.get("days")) and fc.get("precip_next_3d_mm") is not None:
            lines.append(
                f"{place} next 3 days {_fmt(fc.get('precip_next_3d_mm'))} mm, "
                f"7 days {_fmt(fc.get('precip_7d_mm'))} mm."
            )
        outlook = list((fc.get("outlook_days") or [])[:7])
        if single_day:
            outlook = [r for r in outlook if isinstance(r, dict) and str(r.get("date") or "")[:10] == wstart]
        for row in outlook:
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
    seen_rank: set[str] = set()
    for key, rank in collected.items():
        if not (key == "rank" or str(key).startswith("rank:")):
            continue
        if not isinstance(rank, dict):
            continue
        ranked = rank.get("ranked")
        if not ranked:
            continue
        st = str(rank.get("state") or "")
        if st.lower() in seen_rank:
            continue
        seen_rank.add(st.lower())
        metric = rank.get("metric") or "flood"
        lines.append(f"{st} {metric} ranking (3-day rain, Open-Meteo + local-ml):")
        for i, r in enumerate(ranked[:8], 1):
            if not isinstance(r, dict):
                continue
            lines.append(
                f"{i}. {r.get('district')} — score {_fmt(r.get('flood_score'))}, "
                f"{_fmt(r.get('precip_3d_mm'))} mm"
            )
    sw = collected.get("states_weather") or {}
    srows = sw.get("ranked") if isinstance(sw, dict) else None
    if srows and not seen_rank:
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


def generate_actionable_advice(domain: str, metrics: dict[str, Any], condition: str = "", activity: str | None = None) -> str:
    """Generate concise, practical, domain-specific actionable advice."""
    rain_mm = float(metrics.get("precip_mm") or metrics.get("precip_1h_mm") or 0.0)
    rain_prob = float(metrics.get("precip_prob_pct") or 0.0)
    temp_max = float(metrics.get("temp_max_c") or metrics.get("temp_c") or 28.0)
    temp = float(metrics.get("temp_c") or temp_max)
    wind = float(metrics.get("wind_kmh") or metrics.get("wind_speed_max_kmh") or 12.0)
    aqi = metrics.get("aqi")
    p_interrupt = float(metrics.get("p_interrupt_90m") or 0.0)
    flood = float(metrics.get("flood_score") or 0.0)
    sky = str(metrics.get("sky_label") or condition or "").lower()
    act = (activity or "").lower()

    if act in ("skydiving", "skydive", "paragliding", "paraglide"):
        if wind >= 25:
            return f"Surface winds near {_fmt(wind)} km/h exceed safe canopy thresholds; delay jumps until wind settles."
        if rain_mm > 0.5 or rain_prob >= 40 or "rain" in sky or "thunder" in sky:
            return "Precipitation and low cloud ceiling restrict flight visibility; suspend dropzone jumps."
        return "Surface winds and cloud clearances are within typical canopy limits; verify local dropzone NOTAMs and upper-level wind shear."

    if act in ("swim", "swimming"):
        if rain_mm >= 2.0 or rain_prob >= 50 or "thunder" in sky or "rain" in sky:
            return "Showers and lightning hazards make outdoor swimming unsafe; avoid open water or outdoor pools."
        if wind >= 24:
            return f"Brisk winds near {_fmt(wind)} km/h cause choppy waves; avoid swimming in open sea or unpatrolled beaches."
        if temp_max <= 20:
            return f"Cool daytime temperature of {_fmt(temp_max)}°C; water may be chilly for extended swimming."
        return "Calm weather and warm daytime temperatures are favorable for swimming and pool activities."

    if act in ("fishing", "finishing", "angling"):
        if wind >= 25 or rain_mm >= 10:
            return "Gusty winds and heavy showers make water conditions rough; hold off on fishing trips until weather settles."
        if rain_mm >= 2.0 or rain_prob >= 40:
            return "Light precipitation expected; keep waterproof gear handy along riverbanks or piers."
        return "Favorable atmospheric conditions with light winds; good for outdoor fishing and shoreline activities."

    if domain == "aviation":
        if wind >= 28:
            return f"Brisk winds of {_fmt(wind)} km/h may cause turbulence or crosswind issues; evaluate drone and VFR operational limits."
        if rain_mm > 1.5 or "rain" in sky or "thunder" in sky:
            return "Precipitation and reduced visibility limit VFR conditions; delay flights until the shower band clears."
        if rain_prob >= 50:
            return "Incoming precipitation chances may lower cloud bases; maintain a short return-to-base buffer."
        return "Wind and visibility conditions are steady and favorable for UAV or light aircraft operations."

    if domain == "disaster":
        if flood >= 60 or rain_mm >= 35 or "thunder" in sky:
            return "Heightened inundation potential; verify municipal drainage gates and advise vulnerable low-lying settlements."
        if rain_mm >= 12 or flood >= 40:
            return "Moderate rain expected; maintain routine observation on drainage channels and canal embankments."
        return "Disaster and hydrological threat indicators are low; normal baseline monitoring is advised."

    if domain == "farming":
        if rain_mm >= 3.0 or rain_prob >= 60 or p_interrupt >= 0.5:
            return "Postpone irrigation and fertilizer application to prevent nutrient runoff; keep field runoff channels open."
        if temp_max >= 36:
            return "Elevated daytime temperatures will increase evaporation; consider early morning or dusk irrigation."
        if wind >= 22:
            return "Wind speeds could cause agrochemical spray drift; reschedule foliar treatments."
        return "Favorable dry conditions for field weeding, pesticide application, scheduled watering, or harvesting."

    if domain == "marine":
        if wind >= 32 or rain_mm >= 15:
            return "Rough coastal sea conditions and gusty squalls; small fishing craft should avoid venturing offshore."
        if wind >= 20:
            return "Moderate swell along coastal waters; exercise vigilance near harbor entrances and shallow channels."
        return "Calm sea state and nominal tidal flow; favorable for harbor navigation and coastal fishing."

    # urban / general resident
    if rain_mm >= 2.0 or rain_prob >= 50 or p_interrupt >= 0.4:
        return "Carry an umbrella and expect possible transit delays during active shower windows."
    if temp_max >= 35 or temp >= 35:
        return "High daytime heat; stay hydrated and minimize strenuous outdoor exposure during the peak afternoon."
    if aqi is not None and isinstance(aqi, (int, float)) and aqi >= 180:
        return "Air quality is degraded; sensitive individuals should wear masks outdoors."
    if temp_max <= 14:
        return "Cool temperatures; keep a warm layer handy for morning and evening commutes."
    return "Stable and comfortable atmospheric conditions—great for travel, commuting, or outdoor recreation."


def format_card_overview(
    collected: dict[str, Any],
    window: dict[str, str] | None = None,
    domain: str = "urban",
    query: str = "",
    activity: str | None = None,
) -> str:
    """Card-overview style brief summary with 1–3 essential metrics and 1 actionable advice."""
    wstart = str((window or {}).get("start") or "")[:10]
    wend = str((window or {}).get("end") or "")[:10]
    clock = (window or {}).get("hour")
    single_day = bool(wstart and wend and wstart == wend)

    lines: list[str] = []

    # 1. Ranking query
    rank_pack = next((v for k, v in collected.items() if (k == "rank" or str(k).startswith("rank:")) and isinstance(v, dict)), None)
    if rank_pack and rank_pack.get("ranked"):
        ranked = rank_pack.get("ranked") or []
        st = str(rank_pack.get("state") or "")
        metric = str(rank_pack.get("metric") or "flood")
        top_items = []
        for i, r in enumerate(ranked[:3], 1):
            if isinstance(r, dict):
                score = _fmt(r.get("flood_score") or r.get("score") or r.get("precip_3d_mm"))
                top_items.append(f"{i}. {r.get('district')} ({score})")
        lines.append(f"Top {metric} districts in {st}: " + ", ".join(top_items) + ".")
        top_precip = float((ranked[0] if ranked and isinstance(ranked[0], dict) else {}).get("precip_3d_mm") or 0.0)
        lines.append(generate_actionable_advice(domain, {"precip_mm": top_precip, "flood_score": 60 if top_precip > 50 else 30}, activity=activity))
        return " ".join(lines).strip()

    win = collected.get("rain_window")
    fc = collected.get("forecast")
    nc = collected.get("nowcast")
    aqi_pack = collected.get("aqi")
    warns = collected.get("warnings")
    q_low = (query or "").lower()

    # 2. AQI prioritized if asked specifically
    if aqi_pack and any(w in q_low for w in ("aqi", "air", "pollution", "pm2", "smog")):
        cpcb = aqi_pack.get("cpcb") or {}
        val = cpcb.get("value") if isinstance(cpcb, dict) else aqi_pack.get("om_us_aqi")
        place = str(aqi_pack.get("place") or "The area").split(",")[0].strip()
        if val is not None:
            cat = (cpcb.get("category") if isinstance(cpcb, dict) else "Moderate") or "Moderate"
            lines.append(f"In {place}, the air quality index is {_fmt(val)} ({cat}).")
            lines.append(generate_actionable_advice(domain, {"aqi": val}, activity=activity))
            return " ".join(lines).strip()

    # 3. Weather / forecast / single-day window
    target_row: dict[str, Any] | None = None
    place_name = ""
    if isinstance(fc, dict) and fc:
        place_name = str(fc.get("place") or fc.get("label") or "").split(",")[0].strip()
        days = list(fc.get("outlook_days") or [])
        if single_day and wstart:
            target_row = next((r for r in days if isinstance(r, dict) and str(r.get("date") or "")[:10] == wstart), None)
        if not target_row and days and isinstance(days[0], dict):
            target_row = days[0]

    if isinstance(win, dict) and win:
        loc = win.get("location") or {}
        if not place_name:
            place_name = str(loc.get("place_name") or loc.get("district") or loc.get("label") or "").split(",")[0].strip()
        wdays = list(win.get("days") or [])
        if single_day and wstart:
            target_row = next((r for r in wdays if isinstance(r, dict) and str(r.get("date") or "")[:10] == wstart), target_row)
        if not target_row and wdays and isinstance(wdays[0], dict):
            target_row = wdays[0]

    if target_row or (isinstance(fc, dict) and fc):
        place = place_name or "This area"
        cur_temp = fc.get("temp_c") if isinstance(fc, dict) else None
        max_temp = target_row.get("temp_max_c") if target_row else None
        temp_val = cur_temp if cur_temp is not None else max_temp
        rain_val = (target_row.get("precip_mm") if target_row else None) or (fc.get("precip_1h_mm") if isinstance(fc, dict) else 0.0)
        rain_prob = target_row.get("precip_prob_pct") if target_row else None
        sky = (target_row.get("sky_label") if target_row else None) or (fc.get("sky_label") if isinstance(fc, dict) else None) or "fair"
        wind_val = (target_row.get("wind_speed_max_kmh") if target_row else None)
        p3d = fc.get("precip_next_3d_mm") if isinstance(fc, dict) else None

        time_tag = ""
        if single_day and wstart:
            time_tag = f"on {wstart}"
            if clock is not None and clock != "":
                time_tag += f" around {clock}:00 IST"
        else:
            time_tag = "today"

        overview_parts = [f"{place} {time_tag} will see {sky.lower()} skies"]
        if cur_temp is not None and max_temp is not None and abs(float(cur_temp) - float(max_temp)) > 1:
            overview_parts.append(f"temperatures around {_fmt(cur_temp)}°C to {_fmt(max_temp)}°C")
        elif temp_val is not None:
            overview_parts.append(f"temperatures near {_fmt(temp_val)}°C")
        if rain_val is not None:
            prob_str = f" ({rain_prob}%)" if rain_prob is not None else ""
            overview_parts.append(f"rain {_fmt(rain_val)} mm{prob_str}")
        if p3d is not None and float(p3d) > 0:
            overview_parts.append(f"{_fmt(p3d)} mm in 3 days")
        if wind_val is not None and float(wind_val) > 15:
            overview_parts.append(f"winds up to {_fmt(wind_val)} km/h")

        sentence1 = overview_parts[0] + " with " + ", ".join(overview_parts[1:]) + "."
        lines.append(sentence1)

        metrics_for_advice = {
            "precip_mm": rain_val,
            "precip_prob_pct": rain_prob,
            "temp_max_c": max_temp or temp_val,
            "temp_c": cur_temp or temp_val,
            "wind_kmh": wind_val,
            "sky_label": sky,
        }
        lines.append(generate_actionable_advice(domain, metrics_for_advice, condition=sky, activity=activity))
        return " ".join(lines).strip()

    # 3. Nowcast overview
    if isinstance(nc, dict) and nc:
        place = str(nc.get("place") or "The area").split(",")[0].strip()
        locked = (nc.get("nowcast") if isinstance(nc, dict) else None) or {}
        pump = (nc.get("pump") if isinstance(nc, dict) else None) or {}
        p_int = locked.get("p_interrupt_90m")
        if p_int is None:
            p_int = pump.get("p_interrupt_90m")
        onset = locked.get("onset")
        enter = locked.get("enterable_2h")

        nc_parts = [f"In {place}, the next 0–6 hours are active"]
        if p_int is not None:
            nc_parts.append(f"90-min rain interruption chance is {_fmt(p_int)}")
        if onset:
            nc_parts.append(f"rain onset around {onset.split('T')[-1][:5] if 'T' in str(onset) else onset}")
        if enter is not None:
            nc_parts.append("field access is open" if enter else "field access is restricted")

        lines.append("; ".join(nc_parts) + ".")
        lines.append(generate_actionable_advice(domain, {"p_interrupt_90m": p_int, "precip_mm": 2.0 if (p_int and float(p_int) > 0.4) else 0.0}, activity=activity))
        return " ".join(lines).strip()

    # 4. AQI overview
    if isinstance(aqi_pack, dict) and aqi_pack:
        cpcb = aqi_pack.get("cpcb") or {}
        val = cpcb.get("value") if isinstance(cpcb, dict) else aqi_pack.get("om_us_aqi")
        place = str(aqi_pack.get("place") or "The area").split(",")[0].strip()
        if val is not None:
            cat = (cpcb.get("category") if isinstance(cpcb, dict) else "Moderate") or "Moderate"
            lines.append(f"In {place}, the air quality index is {_fmt(val)} ({cat}).")
            lines.append(generate_actionable_advice(domain, {"aqi": val}, activity=activity))
            return " ".join(lines).strip()

    # 5. Warnings overview
    if isinstance(warns, dict) and warns.get("warnings"):
        wlist = warns.get("warnings") or []
        lines.append(f"Active alerts: {len(wlist)} weather warning(s) currently issued for this sector.")
        lines.append(generate_actionable_advice(domain, {"precip_mm": 20.0}, condition="thunderstorm", activity=activity))
        return " ".join(lines).strip()

    return ""


def present_answer(
    collected: dict[str, Any],
    window: dict[str, str] | None = None,
    compact: bool = True,
    domain: str | None = None,
    query: str | None = None,
    activity: str | None = None,
) -> str:
    """If compact is True, formats as a concise conversational card-overview. Otherwise returns full quote_facts."""
    if compact and collected:
        overview = format_card_overview(
            collected,
            window=window,
            domain=domain or "urban",
            query=query or "",
            activity=activity,
        )
        if overview:
            return overview
    return quote_facts(collected, window=window)


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

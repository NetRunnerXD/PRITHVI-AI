"""Structured hi/bn answers from tool JSON. No mid-sentence English splicing."""

from __future__ import annotations

from typing import Any


def compose_indic(locale: str, intent: str, snap: Any, collected: dict[str, Any]) -> str | None:
    if locale not in {"hi", "bn"}:
        return None
    if intent == "rank":
        return _rank(locale, collected)
    if intent in {"irrigation", "rain", "flood"}:
        return _weather(locale, snap, collected)
    if intent == "aqi":
        return _aqi(locale, collected, snap)
    if intent == "list":
        return _list(locale, collected)
    if intent == "price":
        return _price(locale, collected)
    if intent == "outlook":
        return _outlook(locale, snap)
    if intent == "window":
        pack = collected.get("get_rain_window") or collected.get("get_weather_forecast")
        if pack and pack.get("days"):
            from app.services.rain_window import format_indic

            return format_indic(pack, locale)
    if intent == "compare":
        return _compare(locale, collected) or _general(locale, snap)
    return _general(locale, snap)


def _outlook(locale: str, snap: Any) -> str | None:
    p = snap.predictive
    loc = snap.location.label
    days = list(p.outlook_days or [])[:5]
    if locale == "bn":
        lines = [
            f"{loc}: ৭ দিনে বৃষ্টি {p.precip_7d_mm} মিমি, জল ভারসাম্য {p.water_balance_7d_mm} মিমি।",
            f"আগামী ৩ দিন {p.precip_next_3d_mm} মিমি।",
        ]
        for d in days:
            date = d.get("date") or ""
            lines.append(f"{date}: {d.get('precip_mm')} মিমি, সম্ভাবনা {d.get('precip_prob_pct')}%")
        return "\n".join(lines)
    lines = [
        f"{loc}: 7 दिन बारिश {p.precip_7d_mm} मिमी, जल संतुलन {p.water_balance_7d_mm} मिमी।",
        f"अगले 3 दिन {p.precip_next_3d_mm} मिमी।",
    ]
    for d in days:
        date = d.get("date") or ""
        lines.append(f"{date}: {d.get('precip_mm')} मिमी, संभावना {d.get('precip_prob_pct')}%")
    return "\n".join(lines)


def _compare(locale: str, collected: dict) -> str | None:
    src = collected.get("compare_districts") or {}
    delta = src.get("delta_a_minus_b") or src.get("delta") or {}
    if not delta and not src:
        return None
    a = (src.get("a") or {}).get("district") or src.get("district_a") or ""
    b = (src.get("b") or {}).get("district") or src.get("district_b") or ""
    rain = delta.get("rain_3d_mm")
    flood = delta.get("flood_score")
    if locale == "bn":
        return f"{a} বনাম {b}: ৩ দিনের বৃষ্টির ব্যবধান {rain} মিমি, বন্যা স্কোর ব্যবধান {flood}।"
    return f"{a} बनाम {b}: 3 दिन बारिश अंतर {rain} मिमी, बाढ़ स्कोर अंतर {flood}।"


def _general(locale: str, snap: Any) -> str | None:
    if snap is None:
        return None
    loc = snap.location
    p = snap.predictive
    cur = snap.descriptive.current
    sky = cur.sky_label or ""
    act = (snap.prescriptive.actions or [None])[0]
    if locale == "bn":
        bits = [
            f"{loc.label}-এ এখন {sky or 'আকাশের তথ্য'}"
            + (f", {cur.temp_c:.1f}°C" if cur.temp_c is not None else "")
            + "।",
            f"আগামী ৩ দিনে {p.precip_next_3d_mm} মিমি বৃষ্টি, ৭ দিনে {p.precip_7d_mm} মিমি।",
        ]
        if cur.aqi is not None:
            bits.append(f"CPCB AQI {cur.aqi} ({cur.aqi_category or ''})।".replace(" ()", "।"))
        if act and act.action:
            bits.append(act.action)
        return "\n".join(bits)
    bits = [
        f"{loc.label} में अभी {sky or 'मौसम'}"
        + (f", {cur.temp_c:.1f}°C" if cur.temp_c is not None else "")
        + "।",
        f"अगले 3 दिन {p.precip_next_3d_mm} मिमी बारिश, 7 दिन {p.precip_7d_mm} मिमी।",
    ]
    if cur.aqi is not None:
        bits.append(f"CPCB AQI {cur.aqi} ({cur.aqi_category or ''})।".replace(" ()", "।"))
    if act and act.action:
        bits.append(act.action)
    return "\n".join(bits)


def _rank(locale: str, collected: dict) -> str | None:
    src = collected.get("rank_districts") or {}
    ranked = src.get("ranked") or []
    if not ranked:
        return None
    state = src.get("state") or ""
    metric = src.get("metric") or "flood"
    if locale == "bn":
        lines = [f"{state}-এ {metric} র‌্যাঙ্ক (লাইভ মডেল, Open-Meteo + local-ml):"]
        for i, r in enumerate(ranked[:12], 1):
            lines.append(
                f"{i}. {r.get('district')} — বন্যা স্কোর {r.get('flood_score')}, "
                f"৩ দিনে বৃষ্টি {r.get('precip_3d_mm')} মিমি"
            )
        return "\n".join(lines)
    lines = [f"{state} में {metric} रैंकिंग (लाइव मॉडल):"]
    for i, r in enumerate(ranked[:12], 1):
        lines.append(
            f"{i}. {r.get('district')} — बाढ़ स्कोर {r.get('flood_score')}, "
            f"3 दिन बारिश {r.get('precip_3d_mm')} मिमी"
        )
    return "\n".join(lines)


def _weather(locale: str, snap: Any, collected: dict) -> str | None:
    loc = snap.location
    p = snap.predictive
    soil = snap.descriptive.current.soil_moisture_m3m3
    hold = next((a for a in snap.prescriptive.actions if a.id == "hold_irrigation"), None)
    rain = p.precip_next_3d_mm
    if locale == "bn":
        lines = [
            f"{loc.label}-এ আগামী ৩ দিনে আনুমানিক {rain} মিমি বৃষ্টি।",
            f"মাটির আর্দ্রতা {soil:.3f} ঘনমিটার/ঘনমিটার।" if soil is not None else "",
        ]
        nc = (getattr(snap, "science", None) or {}).get("nowcast") or {}
        if (nc.get("pump") or {}).get("action") == "hold":
            lines.append(
                f"আগামী ৯০ মিনিট পাম্প চালাবেন না। বাধার সম্ভাবনা {nc['pump'].get('p_interrupt_90m')}।"
            )
        if hold and hold.quant.water_saved_liters_min:
            lines.append(
                f"এখন অতিরিক্ত সেচ না দেওয়াই ভালো। এতে প্রায় "
                f"{hold.quant.water_saved_liters_min}–{hold.quant.water_saved_liters_max} লিটার জল বাঁচতে পারে।"
            )
        elif rain < 8:
            lines.append("বৃষ্টি কম, হালকা সেচ বিবেচনা করা যেতে পারে।")
        else:
            lines.append("মাঝারি বৃষ্টির সম্ভাবনায় আজ সেচ না দিলেই ভালো।")
        return "\n".join(x for x in lines if x)
    lines = [
        f"{loc.label} में अगले 3 दिन लगभग {rain} मिमी बारिश।",
        f"मिट्टी की नमी {soil:.3f} घन मीटर/घन मीटर।" if soil is not None else "",
    ]
    nc = (getattr(snap, "science", None) or {}).get("nowcast") or {}
    if (nc.get("pump") or {}).get("action") == "hold":
        lines.append(f"अगले 90 मिनट पंप न चलाएँ। रुकने की संभावना {nc['pump'].get('p_interrupt_90m')}।")
    if hold and hold.quant.water_saved_liters_min:
        lines.append(
            f"आज सिंचाई न करें। इससे लगभग "
            f"{hold.quant.water_saved_liters_min}–{hold.quant.water_saved_liters_max} लीटर पानी बच सकता है।"
        )
    else:
        lines.append("बारिश कम हो तो हल्की सिंचाई सोचें, वरना रोकें।")
    return "\n".join(x for x in lines if x)


def _aqi(locale: str, collected: dict, snap: Any) -> str | None:
    block = collected.get("get_air_quality") or {}
    cpcb = block.get("cpcb") or (snap.ogd or {}).get("aqi") or {}
    if not cpcb or cpcb.get("value") is None:
        return None
    place = cpcb.get("queried_place") or snap.location.district
    city = cpcb.get("city") or ""
    station = cpcb.get("station") or ""
    local = cpcb.get("is_local_station")
    dist = cpcb.get("distance_km")
    if locale == "bn":
        where = (
            f"{place}-র CPCB স্টেশন: {station} ({city})।"
            if local
            else f"{place}-র নিজস্ব CPCB স্টেশন পাওয়া যায়নি। নিকটতম স্টেশন: {station}, {city}"
            + (f" ({dist} কিমি দূরে)" if dist is not None else "")
            + "।"
        )
        return (
            f"{where} জাতীয় AQI {cpcb.get('value')} ({cpcb.get('category')})। "
            f"প্রধান দূষক {cpcb.get('dominant_pollutant')}।"
            f" এটি {place} শহরের রিডিং নয় — {city} স্টেশনের।"
            if not local
            else f"{where} জাতীয় AQI {cpcb.get('value')} ({cpcb.get('category')})। প্রধান দূষক {cpcb.get('dominant_pollutant')}।"
        )
    where = (
        f"{place} का CPCB स्टेशन: {station} ({city})।"
        if local
        else f"{place} में CPCB स्टेशन नहीं मिला। निकटतम: {station}, {city}"
        + (f" ({dist} किमी)" if dist is not None else "")
        + "।"
    )
    extra = "" if local else f" यह {place} शहर का रीडिंग नहीं है।"
    return (
        f"{where} राष्ट्रीय AQI {cpcb.get('value')} ({cpcb.get('category')})। "
        f"मुख्य प्रदूषक {cpcb.get('dominant_pollutant')}।{extra}"
    )


def _list(locale: str, collected: dict) -> str | None:
    src = collected.get("list_districts") or {}
    names = [d.get("district") for d in (src.get("districts") or []) if d.get("district")]
    if not names:
        names = src.get("names") or []
    if not names:
        return None
    state = src.get("state") or ""
    head = f"{state}-এর জেলা ({len(names)}টি): " if locale == "bn" else f"{state} के ज़िले ({len(names)}): "
    return head + ", ".join(names)


def _price(locale: str, collected: dict) -> str | None:
    src = collected.get("get_state_mandi") or {}
    grouped = src.get("districts") or {}
    if not grouped:
        rows = (collected.get("get_mandi_prices") or {}).get("mandi") or []
        if not rows:
            return None
        bits = [f"{r.get('commodity')} {int(r.get('modal_price'))}" for r in rows[:6] if r.get("modal_price")]
        return (("আজকের মান্ডি: " if locale == "bn" else "आज की मंडी: ") + "; ".join(bits))
    lines = []
    for dist, rows in list(grouped.items())[:10]:
        if not rows:
            continue
        top = rows[0]
        lines.append(f"{dist}: {top.get('commodity')} {int(top.get('modal_price') or 0)}")
    head = "মান্ডি (INR/কুইন্টাল): " if locale == "bn" else "मंडी (INR/क्विंटल): "
    return head + " | ".join(lines)


def translate_reply(text: str, locale: str, **kwargs: Any) -> str:
    """Do not splice fragments into English. Prefer compose_indic; else keep English."""
    if locale not in {"hi", "bn"} or not text:
        return text
    snap = kwargs.get("snap")
    collected = kwargs.get("collected") or {}
    intent = kwargs.get("intent") or ""
    structured = compose_indic(locale, intent, snap, collected) if snap is not None else None
    if structured:
        return structured
    return text

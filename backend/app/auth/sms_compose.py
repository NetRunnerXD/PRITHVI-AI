"""Hyper-local alert SMS. Start/end of the hazard, never place+now. ≤160 chars."""

from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from typing import Any

from app.auth.sms import SMS_MAX, demo_phone
from app.i18n.number_lock import allowed_from_tools, ungrounded
from app.llm import ollama_client
from app.schemas.dashboard import DashboardSnapshot

IST = timezone(timedelta(hours=5, minutes=30))
_MONTH = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")
_KIND = {
    "lightning": "lightning",
    "thunderstorm": "thunderstorm",
    "flood": "flood",
    "rainfall": "heavy rain",
    "heatwave": "heatwave",
    "fog": "fog",
    "uv": "high UV",
    "landslide": "landslide",
    "aqi": "air quality",
    "fire": "fire",
    "marine": "rough sea",
    "wind": "strong wind",
    "cyclone": "cyclone",
    "cloudburst": "cloudburst",
    "extreme_rain": "very heavy rain",
    "tsunami": "tsunami",
    "seismic": "earthquake",
    "drought": "dry spell",
    "weather": "weather",
}
_DISCLAIM = re.compile(
    r"\s*(I only quote figures from Prithvi AI data\.?|I only quote figures\.?)\s*",
    re.I,
)
_CHATTY = re.compile(
    r"\b(please|you should|stay safe|as of|right now|currently|hello|dear)\b",
    re.I,
)


def fmt_ist(raw: Any, *, with_ist: bool = True) -> str | None:
    """ISO → '15 Sep, 4:30 pm IST'."""
    dt = _as_ist(raw)
    if dt is None:
        return None
    h = dt.hour
    ampm = "am" if h < 12 else "pm"
    h12 = h % 12 or 12
    clock = f"{h12}:{dt.minute:02d} {ampm}" if dt.minute else f"{h12} {ampm}"
    label = f"{dt.day} {_MONTH[dt.month - 1]}, {clock}"
    return f"{label} IST" if with_ist else label


def fmt_span(start: Any, end: Any) -> str:
    """'from 15 Sep, 10:20 pm to 16 Sep, 6 am IST' — IST once, at the end."""
    sdt, edt = _as_ist(start), _as_ist(end)
    if sdt is None and edt is None:
        a, b = str(start or ""), str(end or "")
        return f"from {a.replace(' IST', '')} to {b}".strip()
    if sdt is None:
        return f"until {fmt_ist(end)}"
    if edt is None:
        return f"from {fmt_ist(start)}"
    same_day = sdt.date() == edt.date()
    left = fmt_ist(sdt, with_ist=False)
    if same_day:
        h = edt.hour
        ampm = "am" if h < 12 else "pm"
        h12 = h % 12 or 12
        clock = f"{h12}:{edt.minute:02d} {ampm}" if edt.minute else f"{h12} {ampm}"
        return f"from {left} to {clock} IST"
    return f"from {left} to {fmt_ist(edt)}"


def _as_ist(raw: Any) -> datetime | None:
    if raw is None or raw == "":
        return None
    if isinstance(raw, datetime):
        dt = raw
    else:
        s = str(raw).strip()
        if not s or s in {"?", "—", "-"}:
            return None
        if "IST" in s and re.search(r"\b(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\b", s):
            dt = _parse_pretty(s)
            if dt is None:
                return None
        else:
            dt = _parse_dt(s)
            if dt is None:
                return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=IST)
    return dt.astimezone(IST)


def _parse_pretty(s: str) -> datetime | None:
    m = re.search(
        r"(\d{1,2})\s+(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec),?\s+(\d{1,2})(?::(\d{2}))?\s*(am|pm)",
        s,
        re.I,
    )
    if not m:
        return None
    day = int(m.group(1))
    month = _MONTH.index(m.group(2)[:3].title()) + 1
    h = int(m.group(3))
    minute = int(m.group(4) or 0)
    if m.group(5).lower() == "pm" and h != 12:
        h += 12
    if m.group(5).lower() == "am" and h == 12:
        h = 0
    year = datetime.now(IST).year
    return datetime(year, month, day, h, minute, tzinfo=IST)


def _parse_dt(s: str) -> datetime | None:
    s = s.strip()
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    try:
        return datetime.fromisoformat(s)
    except ValueError:
        pass
    t = s.replace(" ", "T")
    for n, fmt in ((19, "%Y-%m-%dT%H:%M:%S"), (16, "%Y-%m-%dT%H:%M"), (10, "%Y-%m-%d")):
        try:
            return datetime.strptime(t[:n], fmt)
        except ValueError:
            continue
    return None


def _num(v: Any, nd: int | None = None) -> str | None:
    if v is None or v == "":
        return None
    try:
        x = float(v)
    except (TypeError, ValueError):
        return None
    if nd == 0 or (nd is None and abs(x - round(x)) < 0.05):
        return str(int(round(x)))
    if nd is None:
        nd = 1
    return f"{x:.{nd}f}".rstrip("0").rstrip(".")


def _pin(loc: Any) -> str:
    """Town + district only — the SMS pin, no clock."""
    place = (getattr(loc, "place_name", None) or "").strip()
    district = (getattr(loc, "district", None) or "").strip()
    if place and district and place.lower() != district.lower():
        pin = f"{place}, {district}"
    else:
        pin = place or district or "Local"
    if len(pin) > 42:
        pin = (place or district or "Local")[:42]
    return pin


def _pair(start: Any, end: Any, lock: dict[str, Any]) -> tuple[str, str]:
    """Always a hazard window. Never 'as of now' on the place line."""
    sdt = _as_ist(start) or _as_ist(lock.get("onset"))
    edt = _as_ist(end) or _as_ist(lock.get("cessation"))
    if sdt and not edt:
        edt = sdt + timedelta(hours=6)
    elif edt and not sdt:
        sdt = edt - timedelta(hours=6)
    elif not sdt and not edt:
        hours = lock.get("hours") or []
        wet = [h for h in hours if isinstance(h, dict) and float(h.get("mm") or 0) >= 0.4]
        if wet:
            sdt = _as_ist(wet[0].get("t"))
            edt = _as_ist(wet[-1].get("t"))
        if not sdt:
            sdt = datetime.now(IST).replace(minute=0, second=0, microsecond=0)
        if not edt:
            edt = sdt + timedelta(hours=6)
    if edt <= sdt:
        edt = sdt + timedelta(hours=6)
    return fmt_ist(sdt) or "", fmt_ist(edt) or ""


def _window_for(w: Any, lock: dict[str, Any]) -> tuple[Any, Any]:
    start = getattr(w, "window_start", None) or lock.get("onset")
    end = getattr(w, "window_end", None) or getattr(w, "expires_at", None) or lock.get("cessation")
    eta = getattr(w, "eta_min", None)
    if start and not end and eta is not None:
        dt = _as_ist(start)
        try:
            mins = float(eta)
        except (TypeError, ValueError):
            mins = None
        if dt is not None and mins is not None and mins > 0:
            end = dt + timedelta(minutes=max(mins, 60))
    return start, end


def facts_pack(snap: DashboardSnapshot) -> dict[str, Any]:
    loc = snap.location
    live = snap.live
    nc = (snap.science or {}).get("nowcast") or {}
    lock = nc.get("locked") if isinstance(nc, dict) else {}
    lock = lock if isinstance(lock, dict) else {}
    pump = nc.get("pump") if isinstance(nc, dict) else {}
    tide = nc.get("tide") if isinstance(nc, dict) else {}
    warnings = []
    for w in (snap.prescriptive.warnings if snap.prescriptive else [])[:4]:
        start, end = _window_for(w, lock)
        kind = _KIND.get((w.kind or w.hazard or "").lower(), (w.kind or "alert").replace("_", " "))
        warnings.append({"kind": kind, "start": start, "end": end})
    primary = warnings[0] if warnings else {"kind": _KIND.get(str(lock.get("alert_word") or "weather").lower(), "weather")}
    start, end = _pair((primary or {}).get("start"), (primary or {}).get("end"), lock)
    kind = (primary or {}).get("kind") or "weather"
    acts: list[str] = []
    if (pump or {}).get("action") == "hold":
        acts.append("hold irrigation")
    if lock.get("enterable_2h") is False:
        acts.append("field closed")
    if lock.get("labour_closed_2h"):
        acts.append("no outdoor work")
    if isinstance(tide, dict) and tide.get("stay_off_ghat"):
        acts.append("stay off ghat")
    return {
        "pin": _pin(loc),
        "kind": kind,
        "start": start,
        "end": end,
        "rain_mm_h": _num(getattr(live, "precip_1h_mm", None), 1),
        "aqi": _num(getattr(live, "aqi", None), 0),
        "acts": acts,
        "warnings": [{"kind": w["kind"], "start": fmt_ist(w.get("start")), "end": fmt_ist(w.get("end"))} for w in warnings],
    }


_HEAD = {
    "lightning": "Lightning",
    "thunderstorm": "A thunderstorm",
    "flood": "Flooding",
    "heavy rain": "Heavy rain",
    "heatwave": "A heatwave",
    "fog": "Dense fog",
    "high UV": "Very high UV",
    "landslide": "A landslide watch",
    "air quality": "Poor air",
    "fire": "Fire nearby",
    "rough sea": "Rough seas",
    "strong wind": "Strong wind",
    "cyclone": "A cyclone watch",
    "cloudburst": "Cloudburst risk",
    "very heavy rain": "Very heavy rain",
    "tsunami": "A tsunami watch",
    "earthquake": "An earthquake",
    "dry spell": "A dry spell",
    "weather": "Severe weather",
}


def _fit(text: str) -> str:
    text = re.sub(r"\s+", " ", (text or "").strip())
    if len(text) <= SMS_MAX:
        return text
    parts = [p.strip() for p in re.split(r"(?<=\.)\s+", text) if p.strip()]
    while len(" ".join(parts)) > SMS_MAX and len(parts) > 1:
        parts.pop()
    text = " ".join(parts)
    if len(text) > SMS_MAX:
        text = text[: SMS_MAX - 1].rsplit(" ", 1)[0]
        if not text.endswith("."):
            text = text.rstrip(".,;") + "."
    return text[:SMS_MAX]


def _acts(facts: dict[str, Any]) -> list[str]:
    acts = list(facts.get("acts") or [])
    if facts.get("hold_pump") and "hold irrigation" not in acts:
        acts.append("hold irrigation")
    if (facts.get("field_closed") or facts.get("field_open") is False) and "field closed" not in acts:
        acts.append("field closed")
    spoken = []
    for a in acts:
        if a == "hold irrigation":
            spoken.append("hold irrigation")
        elif a == "field closed":
            spoken.append("keep off the field")
        elif a == "no outdoor work":
            spoken.append("avoid outdoor work")
        elif a == "stay off ghat":
            spoken.append("stay off the ghat")
        else:
            spoken.append(a)
    return spoken


def template_sms(facts: dict[str, Any]) -> str:
    pin = facts.get("pin") or facts.get("place") or "this area"
    kind = str(facts.get("kind") or "weather").strip()
    head = _HEAD.get(kind, kind[:1].upper() + kind[1:] if kind else "Severe weather")
    start = facts.get("start")
    end = facts.get("end")
    if not start or not end:
        start, end = _pair(start, end, {})
    sents = [f"{head} is expected in {pin} {fmt_span(start, end)}."]
    rain = facts.get("rain_mm_h")
    try:
        if rain is not None and float(rain) > 0:
            sents.append(f"Rain {rain} mm this hour.")
    except (TypeError, ValueError):
        pass
    aqi = facts.get("aqi")
    try:
        if aqi is not None and float(aqi) >= 200:
            sents.append(f"Air is poor (AQI {aqi}).")
    except (TypeError, ValueError):
        pass
    spoken = _acts(facts)
    if spoken:
        if len(spoken) == 1:
            sents.append(f"{spoken[0][:1].upper() + spoken[0][1:]}.")
        else:
            sents.append(f"{spoken[0][:1].upper() + spoken[0][1:]} and {spoken[1]}.")
    return _fit(" ".join(sents))


def _silent_lock(text: str, facts: dict[str, Any]) -> str:
    blob = _DISCLAIM.sub(" ", text or "")
    blob = re.sub(r"[ \t]+", " ", blob).strip()
    allowed = allowed_from_tools([facts])
    for tok in ungrounded(blob, allowed):
        blob = blob.replace(tok, "", 1)
    blob = re.sub(r"[ \t]+", " ", blob)
    blob = re.sub(r" *\n *", "\n", blob).strip()
    return _fit(blob)


def _has_window(text: str) -> bool:
    t = text or ""
    return bool(re.search(r"\bfrom\b.+\bto\b", t, re.I) or re.search(r"\buntil\b", t, re.I))


async def preview_sms(snap: DashboardSnapshot, *, locale: str = "en") -> dict[str, Any]:
    facts = facts_pack(snap)
    fallback = template_sms(facts)
    used = "template"
    text = fallback
    try:
        ping_ok, _ = await ollama_client.ping()
    except Exception:
        ping_ok = False
    if ping_ok:
        sys = (
            "Rewrite as 1-2 short English sentences for a local weather SMS. "
            "Hard limit 160 characters. Must include the hazard window as "
            "'from <start> to <end>' using those strings unchanged. "
            "Name the town. Be readable, not a data dump. No Start:/End: labels, "
            "no greeting, no 'I only quote figures'."
        )
        try:
            out = await ollama_client.chat(
                [
                    {"role": "system", "content": sys},
                    {"role": "user", "content": fallback + "\n\n" + str(facts)},
                ]
            )
            draft = _DISCLAIM.sub(" ", (out.get("content") or "").strip())
            draft = re.sub(r"\s+", " ", draft).strip()
            if (
                draft
                and _has_window(draft)
                and "Start:" not in draft
                and len(draft) <= SMS_MAX
                and not _CHATTY.search(draft)
            ):
                locked = _silent_lock(draft, facts)
                if locked and _has_window(locked) and len(locked) <= SMS_MAX:
                    text = locked
                    used = "ollama"
        except Exception:
            text = fallback
            used = "template"
    text = _fit(_DISCLAIM.sub(" ", text).strip())
    if not text or not _has_window(text) or len(text) > SMS_MAX:
        text = fallback
        used = "template"
    return {
        "text": text,
        "chars": len(text),
        "max": SMS_MAX,
        "engine": used,
        "to": f"+91 {demo_phone()}",
        "facts": facts,
        "locale": locale,
    }

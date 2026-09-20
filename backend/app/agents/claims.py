"""Span-level numeral check. Swap unbound digits for pack figures; dash only if none."""

from __future__ import annotations

import re
from typing import Any

from app.agents.binder import looks_like_dump
from app.i18n.number_lock import ISO_DATE, NUM, allowed_from_tools, ungrounded, walk_numbers


def walk_payload_nums(payloads: list[Any], acc: set[str]) -> None:
    for p in payloads:
        walk_numbers(p, acc)

_NOTE = "I only quote figures from Prithvi AI data."

_TAIL = re.compile(
    r"^\s*(mm|मिमी|মিমি|°\s*C|°C|deg(?:ree)?s?\s*C|%|pct|AQI|aqi|hPa|km/?h|m/s)\b",
    re.I,
)

_UNIT_KEYS = {
    "mm": ("precip", "rain", "total_mm", "water_balance"),
    "temp": ("temp",),
    "pct": ("pct", "prob", "score", "humidity"),
    "aqi": ("aqi",),
    "hpa": ("pressure", "hpa", "msl"),
    "wind": ("wind", "gust", "kmh"),
}


def _unit_of(blob: str, end: int) -> str | None:
    tail = blob[end : end + 24]
    m = _TAIL.match(tail)
    if not m:
        return None
    t = m.group(1).lower().replace(" ", "")
    if t in {"mm", "मिमी", "মিমি"}:
        return "mm"
    if "c" in t or "deg" in t:
        return "temp"
    if t in {"%", "pct"}:
        return "pct"
    if t == "aqi":
        return "aqi"
    if t == "hpa":
        return "hpa"
    if "km" in t or t == "m/s":
        return "wind"
    return None


def _fmt_num(v: float) -> str:
    if abs(v - round(v)) < 1e-9:
        return str(int(round(v)))
    return f"{v:g}"


def _nums_by_unit(payloads: list[Any]) -> dict[str, list[float]]:
    buckets: dict[str, list[float]] = {k: [] for k in ("mm", "temp", "pct", "aqi", "hpa", "wind", "any")}

    def walk(obj: Any, key: str = "") -> None:
        if obj is None or isinstance(obj, bool):
            return
        if isinstance(obj, dict):
            for k, v in obj.items():
                walk(v, str(k).lower())
            return
        if isinstance(obj, (list, tuple)):
            for v in obj:
                walk(v, key)
            return
        if not isinstance(obj, (int, float)):
            return
        v = float(obj)
        buckets["any"].append(v)
        kl = key
        if any(s in kl for s in _UNIT_KEYS["mm"]):
            buckets["mm"].append(v)
        elif any(s in kl for s in _UNIT_KEYS["temp"]):
            buckets["temp"].append(v)
        elif any(s in kl for s in _UNIT_KEYS["aqi"]):
            buckets["aqi"].append(v)
        elif any(s in kl for s in _UNIT_KEYS["hpa"]):
            buckets["hpa"].append(v)
        elif any(s in kl for s in _UNIT_KEYS["wind"]):
            buckets["wind"].append(v)
        elif any(s in kl for s in _UNIT_KEYS["pct"]):
            buckets["pct"].append(v)

    for p in payloads:
        walk(p)
    return buckets


def _closest(want: float, cands: list[float]) -> float | None:
    if not cands:
        return None
    return min(cands, key=lambda x: abs(x - want))


def check_claims(
    text: str,
    payloads: list[Any],
    window: dict[str, str] | None = None,
) -> tuple[str, list[str]]:
    blob = text or ""
    if looks_like_dump(blob):
        return "", ["dump"]
    scoped = list(payloads)
    wstart = str((window or {}).get("start") or "")[:10]
    wend = str((window or {}).get("end") or "")[:10]
    single = bool(wstart and wend and wstart == wend)
    if single:
        scoped = []
        for p in payloads:
            if not isinstance(p, dict):
                scoped.append(p)
                continue
            need = str(p.get("need") or "")
            if need == "forecast" and p.get("precip_next_3d_mm") is not None:
                p = dict(p)
                p.pop("precip_next_3d_mm", None)
                p.pop("precip_7d_mm", None)
            if need == "rank":
                # rank position 1–N must not license rainfall millimetres
                p = {k: v for k, v in p.items() if k not in {"ranked"}}
            scoped.append(p)
    raw_allowed = allowed_from_tools(scoped)
    years = {"2024", "2025", "2026", "2027", "2028"}
    tiny = {str(i) for i in range(0, 16)}
    payload_nums: set[str] = set()
    walk_payload_nums(scoped, payload_nums)
    allowed = (raw_allowed - tiny) | years | (tiny & payload_nums)
    blob_pay = str(scoped)
    for raw in [wstart, wend] + ISO_DATE.findall(blob_pay):
        if not raw or len(raw) < 10:
            continue
        if not ISO_DATE.fullmatch(raw[:10]) and not ISO_DATE.search(raw):
            continue
        raw = raw[:10]
        if not ISO_DATE.fullmatch(raw):
            continue
        y, mo, d = raw.split("-")
        allowed.add(raw)
        allowed.add(d)
        allowed.add(mo)
        allowed.add(str(int(d)))
        allowed.add(str(int(mo)))
        allowed.add(y)
    iso_spans = [
        (m.start(), m.end())
        for m in ISO_DATE.finditer(blob)
        if m.group(0) in allowed
    ]

    def _in_iso(pos: int) -> bool:
        return any(a <= pos < b for a, b in iso_spans)

    # this-turn payloads only: do not treat the harmless year set as a license for scores
    # but years in _HARMLESS stay so "2026" in a title is ok
    by_unit = _nums_by_unit(scoped)
    out = []
    rejected: list[str] = []
    dashed = False
    last = 0
    for m in NUM.finditer(blob):
        token = m.group(0)
        out.append(blob[last : m.start()])
        if _in_iso(m.start()):
            out.append(token)
            last = m.end()
            continue
        bad = ungrounded(token, allowed)
        if bad:
            rejected.append(token)
            try:
                want = float(token)
            except ValueError:
                want = None
            unit = _unit_of(blob, m.end())
            pool = by_unit.get(unit or "", []) or (by_unit["any"] if unit is None else [])
            hit = _closest(want, pool) if want is not None else None
            if hit is not None:
                out.append(_fmt_num(hit))
            else:
                out.append("—")
                dashed = True
        else:
            out.append(token)
        last = m.end()
    out.append(blob[last:])
    cleaned = "".join(out).strip()
    if dashed and _NOTE.lower() not in cleaned.lower():
        cleaned = (cleaned + " " + _NOTE).strip()
    return cleaned, rejected

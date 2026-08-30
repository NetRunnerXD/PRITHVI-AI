"""Span-level numeral check. Replace unbound digits; never inject a preset answer."""

from __future__ import annotations

from typing import Any

from app.agents.binder import looks_like_dump
from app.i18n.number_lock import ISO_DATE, NUM, allowed_from_tools, ungrounded, walk_numbers


def walk_payload_nums(payloads: list[Any], acc: set[str]) -> None:
    for p in payloads:
        walk_numbers(p, acc)

_NOTE = "I only quote figures from Rituchakra data."


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
    out = []
    rejected: list[str] = []
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
            out.append("—")
            rejected.append(token)
        else:
            out.append(token)
        last = m.end()
    out.append(blob[last:])
    cleaned = "".join(out).strip()
    if rejected:
        if _NOTE.lower() not in cleaned.lower():
            cleaned = (cleaned + " " + _NOTE).strip()
    return cleaned, rejected

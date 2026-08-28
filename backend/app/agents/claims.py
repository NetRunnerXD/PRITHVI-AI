"""Span-level numeral check. Replace unbound digits; never inject a preset answer."""

from __future__ import annotations

from typing import Any

from app.agents.binder import looks_like_dump
from app.i18n.number_lock import ISO_DATE, NUM, allowed_from_tools, ungrounded, walk_numbers


def walk_payload_nums(payloads: list[Any], acc: set[str]) -> None:
    for p in payloads:
        walk_numbers(p, acc)

_NOTE = "I only quote figures from Rituchakra data."


def check_claims(text: str, payloads: list[Any]) -> tuple[str, list[str]]:
    blob = text or ""
    if looks_like_dump(blob):
        return "", ["dump"]
    raw_allowed = allowed_from_tools(payloads)
    years = {"2024", "2025", "2026", "2027", "2028"}
    tiny = {str(i) for i in range(0, 16)}
    payload_nums: set[str] = set()
    walk_payload_nums(payloads, payload_nums)
    allowed = (raw_allowed - tiny) | years | (tiny & payload_nums)
    blob_pay = str(payloads)
    for raw in ISO_DATE.findall(blob_pay) + ISO_DATE.findall(blob):
        y, mo, d = raw.split("-")
        allowed.add(raw)
        allowed.add(d)
        allowed.add(mo)
        allowed.add(str(int(d)))
        allowed.add(str(int(mo)))
        allowed.add(y)
    iso_spans = [(m.start(), m.end()) for m in ISO_DATE.finditer(blob)]

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

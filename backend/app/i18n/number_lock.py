from __future__ import annotations

import re
from typing import Any

# Unsigned figures. A hyphen in 2026-08-28 is a date separator, not minus.
# A leading minus is allowed only at start or after whitespace (" -3.1").
NUM = re.compile(r"(?:(?<=^)|(?<=\s)|(?<=\())-?\d+(?:\.\d+)?|(?<![A-Za-z0-9.])\d+(?:\.\d+)?")
ISO_DATE = re.compile(r"\b\d{4}-\d{2}-\d{2}\b")

# Years and tiny structural counts only. Percents and scores must come from tools.
_HARMLESS = {str(i) for i in range(0, 16)} | {
    "2024", "2025", "2026", "2027", "2028",
}


def walk_numbers(obj: Any, acc: set[str]) -> None:
    if obj is None or isinstance(obj, bool):
        return
    if isinstance(obj, (int, float)):
        acc.add(str(obj))
        acc.add(f"{obj:g}")
        if isinstance(obj, float):
            acc.add(f"{obj:.1f}")
            acc.add(f"{obj:.0f}")
        return
    if isinstance(obj, str):
        for m in NUM.findall(obj):
            acc.add(m)
        return
    if isinstance(obj, dict):
        for v in obj.values():
            walk_numbers(v, acc)
        return
    if isinstance(obj, (list, tuple)):
        for v in obj:
            walk_numbers(v, acc)


def allowed_from_tools(payloads: list[Any]) -> set[str]:
    acc: set[str] = set(_HARMLESS)
    for p in payloads:
        walk_numbers(p, acc)
    return acc


def ungrounded(text: str, allowed: set[str]) -> list[str]:
    found = []
    for m in NUM.findall(text or ""):
        if m in allowed or m in _HARMLESS:
            continue
        try:
            fv = float(m)
            if f"{fv:g}" in allowed or f"{fv:.1f}" in allowed:
                continue
        except ValueError:
            pass
        found.append(m)
    return found


def lock_and_note(text: str, payloads: list[Any]) -> tuple[str, list[str]]:
    """Return text plus any numerals not present in tool payloads."""
    allowed = allowed_from_tools(payloads)
    return text, ungrounded(text, allowed)

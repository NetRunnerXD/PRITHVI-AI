"""Bulk chat eval: compare replies to independently fetched (or fixture) metrics."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.agents.facts import needed_facts
from app.i18n.number_lock import NUM

CASES_PATH = Path(__file__).resolve().parent / "cases.json"

SKIP_NUM = {str(i) for i in range(0, 16)} | {"2024", "2025", "2026", "2027", "2028"}


def load_cases() -> list[dict[str, Any]]:
    return json.loads(CASES_PATH.read_text(encoding="utf-8"))


def significant_numbers(obj: Any) -> set[str]:
    found: set[str] = set()

    def walk(x: Any) -> None:
        if isinstance(x, bool) or x is None:
            return
        if isinstance(x, (int, float)):
            for form in (str(x), f"{x:g}"):
                if form not in SKIP_NUM:
                    found.add(form)
            return
        if isinstance(x, str):
            for m in NUM.findall(x):
                if m not in SKIP_NUM:
                    found.add(m)
            return
        if isinstance(x, dict):
            for v in x.values():
                walk(v)
            return
        if isinstance(x, (list, tuple)):
            for v in x:
                walk(v)

    walk(obj)
    return found


def reply_text(final: dict[str, Any]) -> str:
    bits = [final.get("content_en") or "", final.get("content") or ""]
    for b in final.get("blocks") or []:
        bits.append(json.dumps(b, ensure_ascii=False))
    return "\n".join(bits)


def score_case(case: dict[str, Any], final: dict[str, Any], gold: dict[str, Any], fetched: list[str]) -> dict[str, Any]:
    text = reply_text(final)
    gold_nums = significant_numbers(gold)
    hits = sorted(n for n in gold_nums if n in text)
    traces = [t.get("name") for t in (final.get("tool_trace") or [])]
    if not case.get("weather"):
        bad = [n for n in fetched if n in {"rain_window", "nowcast", "forecast", "aqi", "mandi"}]
        return {
            "id": case["id"],
            "ok": not bad,
            "weather": False,
            "fetched": fetched,
            "hits": hits,
            "reason": "fetched weather" if bad else "ok",
        }
    expect = list(case.get("needs") or [])
    # capability: reason text is enough
    if expect == ["capability"]:
        ok = "radar" in text.lower() or "insat" in text.lower() or "not wired" in text.lower() or "401" in text
        return {"id": case["id"], "ok": ok, "weather": True, "fetched": fetched, "hits": hits, "reason": "capability"}
    if not gold_nums:
        ok = all(e in fetched for e in expect) if expect else True
        return {
            "id": case["id"],
            "ok": ok,
            "weather": True,
            "expect": expect,
            "fetched": fetched,
            "hits": hits,
            "reason": "fetched (no numeric gold)" if ok else "not fetched",
        }
    ok = bool(hits)
    return {
        "id": case["id"],
        "ok": ok,
        "weather": True,
        "expect": expect,
        "fetched": fetched,
        "gold": sorted(gold_nums)[:12],
        "hits": hits,
        "reason": "quoted gold" if ok else "missing gold numbers",
        "traces": traces,
    }


def check_need_detector(case: dict[str, Any]) -> dict[str, Any]:
    got = needed_facts(case["q"])
    expect = case.get("needs") or []
    if not case.get("weather"):
        ok = got == []
    else:
        ok = set(expect).issubset(set(got)) or (not expect)
    return {"id": case["id"], "ok": ok, "expect": expect, "got": got}

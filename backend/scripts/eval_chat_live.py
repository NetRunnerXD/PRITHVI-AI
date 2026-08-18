"""Long live eval: user-style questions, chain, India-wide, refuse, AQI missing.

  cd backend
  python scripts/eval_chat_live.py
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.agents.facts import source_gate  # noqa: E402
from app.agents.orchestrator import run_agent  # noqa: E402
from app.llm import ollama_client  # noqa: E402
from app.schemas.chat import ChatRequest  # noqa: E402
from app.services.location_svc import resolve_location  # noqa: E402

TURNS = [
    {"id": "flood-odisha", "q": "Flood ranking of Odisha", "place": "Bhubaneswar", "want": ["rank"], "refuse": False},
    {"id": "flood-kerala-follow", "q": "what about Kerala?", "place": "Kochi", "want": ["rank"], "refuse": False, "cid": "live-chain"},
    {"id": "flood-odisha-chain0", "q": "Flood ranking of Odisha", "place": "Bhubaneswar", "want": ["rank"], "refuse": False, "cid": "live-chain"},
    {"id": "pet", "q": "Best places to take my pet to visit", "place": "Haldia", "want": [], "refuse": True},
    {"id": "visit-or", "q": "Should I visit Odisha or West Bengal", "place": "Haldia", "want": ["states_weather"], "refuse": False},
    {"id": "best-list", "q": "List the states/districts/cities by weather that are best to visit", "place": "Jaipur", "want": [], "refuse": True},
    {"id": "aqi-jaipur", "q": "AQI in Jaipur", "place": "Jaipur", "want": ["aqi"], "refuse": False},
    {"id": "aqi-haldia", "q": "AQI in Haldia", "place": "Haldia", "want": ["aqi"], "refuse": False},
    {"id": "aqi-puri", "q": "Air quality in Puri", "place": "Puri", "want": ["aqi"], "refuse": False},
    {"id": "rain-chennai", "q": "How much rain in Chennai tomorrow?", "place": "Chennai", "want": ["rain_window"], "refuse": False},
    {"id": "rain-guwahati", "q": "Rain next 5 days in Guwahati", "place": "Guwahati", "want": ["rain_window"], "refuse": False},
    {"id": "hello", "q": "hello there", "place": "Haldia", "want": [], "refuse": False},
]


async def one(case: dict, cid: str | None) -> dict:
    loc = resolve_location(q=case.get("place") or "Haldia")
    payload = ChatRequest(message=case["q"], location=loc, conversation_id=cid)
    fetched: list[str] = []
    final = None
    async for ev in run_agent(payload):
        if ev.get("type") == "tool_start":
            fetched.append((ev.get("args") or {}).get("need") or ev.get("name"))
        if ev.get("type") == "final":
            final = ev["message"]
    text = (final or {}).get("content_en") or (final or {}).get("content") or ""
    gate = source_gate(case["q"])
    ok = True
    reasons = []
    if case.get("refuse"):
        if "Rituchakra" not in text and "cannot" not in text.lower() and "do not" not in text.lower():
            ok = False
            reasons.append("expected refuse")
        if fetched:
            ok = False
            reasons.append(f"fetched on refuse {fetched}")
    else:
        for n in case.get("want") or []:
            if n not in fetched and not any(str(x).startswith(n) for x in fetched):
                # backfill still counts
                if n not in fetched:
                    ok = False
                    reasons.append(f"missing fetch {n}")
        if "AQI 0" in text or "AQI 0 " in text:
            ok = False
            reasons.append("fake AQI 0")
        if case.get("want") and not any(ch.isdigit() for ch in text) and not case.get("refuse"):
            if "no AQI" not in text and "not in" not in text.lower() and "cannot" not in text.lower():
                if case["want"] != ["aqi"]:
                    ok = False
                    reasons.append("no digits in sourced answer")
    return {
        "id": case["id"],
        "ok": ok,
        "reasons": reasons,
        "fetched": fetched,
        "gate": gate.mode,
        "snippet": text[:280],
        "suggestions": [s.get("label") for s in (final or {}).get("suggestions") or []],
    }


async def main() -> int:
    ok, msg = await ollama_client.ping()
    print("ollama", ok, msg, flush=True)
    if not ok:
        return 2
    rows = []
    # seed chain
    await one(
        {"id": "seed", "q": "Flood ranking of Odisha", "place": "Bhubaneswar", "want": ["rank"], "refuse": False},
        "live-chain",
    )
    for case in TURNS:
        print("…", case["id"], flush=True)
        row = await one(case, case.get("cid"))
        rows.append(row)
        print("  ", "OK" if row["ok"] else "FAIL", row["reasons"], row["fetched"], flush=True)
    fails = [r for r in rows if not r["ok"]]
    print(json.dumps({"n": len(rows), "fail": len(fails), "rows": rows}, indent=2, ensure_ascii=False)[:12000])
    return 1 if fails else 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))

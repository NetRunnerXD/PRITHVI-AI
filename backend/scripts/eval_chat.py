"""Live bulk eval: each case vs independently fetched DataLib metrics.

  cd backend
  python scripts/eval_chat.py
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.agents.data_tool import DataLib  # noqa: E402
from app.agents.orchestrator import run_agent  # noqa: E402
from app.llm import ollama_client  # noqa: E402
from app.schemas.chat import ChatRequest  # noqa: E402
from app.services.location_svc import resolve_location  # noqa: E402
from app.agents.eval_llm import load_cases, score_case  # noqa: E402


async def gold_for(case: dict) -> dict:
    loc = resolve_location(q=case.get("place") or "Haldia")
    lib = DataLib(loc, speech=case["q"])
    out = {}
    for need in case.get("needs") or []:
        args = {"need": need, "place": loc.place_name or loc.district, "question": case["q"]}
        if need == "compare":
            args["other"] = "Digha"
        pack = await lib.call(args)
        out[need] = pack
    return out


async def run_one(case: dict) -> dict:
    loc = resolve_location(q=case.get("place") or "Haldia")
    payload = ChatRequest(message=case["q"], location=loc)
    final = None
    fetched: list[str] = []
    async for ev in run_agent(payload):
        if ev.get("type") == "tool_start" and (ev.get("args") or {}).get("need"):
            fetched.append(ev["args"]["need"])
        if ev.get("type") == "final":
            final = ev["message"]
    gold = await gold_for(case) if case.get("weather") else {}
    return score_case(case, final or {}, gold, fetched)


async def main() -> int:
    ok, detail = await ollama_client.ping()
    if not ok:
        print("Ollama down:", detail)
        return 2
    rows = []
    for case in load_cases():
        print("…", case["id"], flush=True)
        row = await run_one(case)
        rows.append(row)
        print("  ", "OK" if row["ok"] else "FAIL", row.get("reason"), row.get("hits"))
    fails = [r for r in rows if not r["ok"]]
    print(json.dumps({"n": len(rows), "fail": len(fails), "rows": rows}, indent=2, default=str)[:8000])
    return 1 if fails else 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))

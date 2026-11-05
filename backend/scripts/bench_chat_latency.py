"""Chat latency: time to first answer text (TTFT) and to the full reply, in-process.

Works on old and new code (old code has no token stream, so TTFT = full reply).
Uses whatever LLM the backend/.env selects; keys are never printed.

  cd backend
  python scripts/bench_chat_latency.py --label after --out bench_after.json
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import statistics
import sys
import time
from pathlib import Path

ROOT = Path(os.environ.get("PRITHVI_BACKEND") or Path(__file__).resolve().parents[1])
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)

from app.agents.orchestrator import run_agent  # noqa: E402
from app.schemas.chat import ChatRequest  # noqa: E402
from app.services.location_svc import resolve_location  # noqa: E402

QUESTIONS = [
    ("en", "Will it rain in Haldia tomorrow?", "auto"),
    ("en-multi", "AQI and any weather alerts in Kolkata?", "auto"),
    ("hi", "क्या कल पटना में बारिश होगी?", "auto"),
    ("bn", "আগামীকাল কলকাতায় বৃষ্টি হবে?", "auto"),
    ("ta", "சென்னையில் நாளை மழை பெய்யுமா?", "auto"),
    ("hinglish", "kal Patna mein barish hogi kya?", "auto"),
]


async def one(q: str, out_locale: str, place: str) -> dict:
    t0 = time.perf_counter()
    first_event = first_text = None
    final = None
    async for ev in run_agent(
        ChatRequest(message=q, location=resolve_location(q=place), output_locale=out_locale)
    ):
        now = time.perf_counter() - t0
        if first_event is None:
            first_event = now
        if ev.get("type") == "delta" and first_text is None:
            first_text = now
        if ev.get("type") == "final":
            final = ev
            if first_text is None:
                first_text = now
    total = time.perf_counter() - t0
    msg = (final or {}).get("message") or {}
    return {
        "first_event_s": round(first_event or total, 3),
        "ttft_s": round(first_text or total, 3),
        "total_s": round(total, 3),
        "locale": msg.get("locale"),
        "chars": len(msg.get("content") or ""),
    }


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--label", default="run")
    ap.add_argument("--reps", type=int, default=2)
    ap.add_argument("--place", default="Haldia")
    ap.add_argument("--sleep", type=float, default=4.0)
    ap.add_argument("--out", default="bench_chat.json")
    ns = ap.parse_args()
    rows = []
    for rep in range(ns.reps):
        for tag, q, out_locale in QUESTIONS:
            try:
                r = await one(q, out_locale, ns.place)
            except Exception as exc:  # noqa: BLE001
                r = {"error": type(exc).__name__}
            r.update(tag=tag, rep=rep)
            rows.append(r)
            print(json.dumps(r, ensure_ascii=False), flush=True)
            await asyncio.sleep(ns.sleep)
    ok = [r for r in rows if "total_s" in r]
    warm = [r for r in ok if r["rep"] > 0] or ok
    summary = {
        "label": ns.label,
        "n": len(ok),
        "ttft_median_s": round(statistics.median(r["ttft_s"] for r in ok), 2) if ok else None,
        "total_median_s": round(statistics.median(r["total_s"] for r in ok), 2) if ok else None,
        "warm_ttft_median_s": round(statistics.median(r["ttft_s"] for r in warm), 2) if warm else None,
        "warm_total_median_s": round(statistics.median(r["total_s"] for r in warm), 2) if warm else None,
    }
    print("SUMMARY", json.dumps(summary))
    Path(ns.out).write_text(json.dumps({"summary": summary, "rows": rows}, indent=1, ensure_ascii=False), encoding="utf-8")


if __name__ == "__main__":
    asyncio.run(main())

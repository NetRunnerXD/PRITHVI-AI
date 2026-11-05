"""Tool-call accuracy: 30 prompts -> expected tool(s) and arguments.

Runs each prompt against the configured free LLM providers (keys from backend/.env,
never printed) with two schemas:
  typed   the 7 typed tools (app/agents/typed_tools.py)
  legacy  the old single data(need=...) function, mapped onto the same names
Scores: right tool set, valid arguments, expected argument values.

  cd backend
  python scripts/eval_tool_calls.py                 # every keyed provider of gemini,groq
  python scripts/eval_tool_calls.py --providers groq --schemas typed --out eval_tools.json
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(os.environ.get("PRITHVI_BACKEND") or Path(__file__).resolve().parents[1])
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)

from app.agents.data_tool import SCHEMA as LEGACY_SCHEMA  # noqa: E402
from app.agents.typed_tools import TOOL_OF_NEED, TOOLS, to_data_args  # noqa: E402
from app.llm import ollama_client  # noqa: E402
from app.llm import providers as registry  # noqa: E402

IST = timezone(timedelta(hours=5, minutes=30))
TODAY = datetime.now(IST).date()
D = lambda n: (TODAY + timedelta(days=n)).isoformat()  # noqa: E731

# (prompt, expected tool set, expected args per tool: value substring, case-insensitive)
CASES: list[tuple[str, set[str], dict[str, dict[str, object]]]] = [
    ("Will it rain in Patna tomorrow?", {"get_forecast"}, {"get_forecast": {"place": "patna"}}),
    ("What's the temperature in Kolkata right now?", {"get_forecast"}, {"get_forecast": {"place": "kolkata"}}),
    ("How hot will Jaipur be at 3 pm today?", {"get_forecast"}, {"get_forecast": {"place": "jaipur", "hour": 15}}),
    ("Weather outlook for Chennai this week", {"get_forecast"}, {"get_forecast": {"place": "chennai"}}),
    (f"How much rain in Guwahati from {D(2)} to {D(4)}?", {"get_forecast"}, {"get_forecast": {"place": "guwahati", "start_date": D(2), "end_date": D(4)}}),
    ("Is it going to rain here in the next hour?", {"get_nowcast"}, {}),
    ("Should I switch off the irrigation pump for the next 90 minutes?", {"get_nowcast"}, {}),
    ("Is a storm coming to Bhubaneswar in the next 3 hours?", {"get_nowcast"}, {"get_nowcast": {"place": "bhubaneswar"}}),
    ("Any IMD warnings for Mumbai?", {"get_alerts"}, {"get_alerts": {"place": "mumbai"}}),
    ("Is there a cyclone alert for the Odisha coast near Puri?", {"get_alerts"}, {"get_alerts": {"place": "puri"}}),
    ("Are there lightning alerts in my area?", {"get_alerts"}, {}),
    ("What's the AQI in Delhi?", {"get_air_quality"}, {"get_air_quality": {"place": "delhi"}}),
    ("Is the air safe for my kids in Lucknow right now?", {"get_air_quality"}, {"get_air_quality": {"place": "lucknow"}}),
    ("Air quality here?", {"get_air_quality"}, {}),
    ("What is the flood risk in Malda?", {"get_risks"}, {"get_risks": {"place": "malda"}}),
    ("Is there heat stress risk in Nagpur?", {"get_risks"}, {"get_risks": {"place": "nagpur"}}),
    ("Do my fields in Bankura need irrigation, what's the drought risk?", {"get_risks"}, {"get_risks": {"place": "bankura"}}),
    ("Compare rain in Haldia and Digha", {"compare_places"}, {"compare_places": {"other": "digha"}}),
    ("Which is wetter right now, Siliguri or Darjeeling?", {"compare_places"}, {}),
    ("Rank the districts of Bihar by flood risk", {"rank_districts"}, {"rank_districts": {"state": "bihar", "metric": "flood"}}),
    ("Which districts in Rajasthan face the worst heat?", {"rank_districts"}, {"rank_districts": {"state": "rajasthan", "metric": "heat"}}),
    ("Top drought-hit districts of Maharashtra", {"rank_districts"}, {"rank_districts": {"state": "maharashtra", "metric": "drought"}}),
    ("AQI and any alerts in Delhi?", {"get_air_quality", "get_alerts"}, {"get_air_quality": {"place": "delhi"}, "get_alerts": {"place": "delhi"}}),
    ("Rain forecast and flood risk for Silchar", {"get_forecast", "get_risks"}, {"get_forecast": {"place": "silchar"}, "get_risks": {"place": "silchar"}}),
    ("kal Patna mein barish hogi kya?", {"get_forecast"}, {"get_forecast": {"place": "patna"}}),
    ("Delhi ka AQI kitna hai abhi?", {"get_air_quality"}, {"get_air_quality": {"place": "delhi"}}),
    ("Hello! Who are you?", set(), {}),
    ("What is a western disturbance?", set(), {}),
    ("Tell me a joke", set(), {}),
    ("Thanks, that's all", set(), {}),
]

SYSTEM = (
    "You are PRITHVI-AI, an Indian weather assistant. Today is {today} (IST). "
    "The user's pinned place is Haldia, West Bengal. Use the provided functions whenever the user "
    "needs weather, nowcast, alerts, air quality, risk, comparison or ranking data; never answer such "
    "questions from memory. Independent lookups may be called in parallel. Leave place empty for the "
    "pinned place. Do not call functions for greetings or general knowledge."
)


def _typed_from_legacy(call: dict) -> tuple[str, dict]:
    try:
        a = json.loads(call.get("arguments") or "{}")
    except ValueError:
        a = {}
    need = str(a.get("need") or "")
    name = TOOL_OF_NEED.get(need, f"data:{need}")
    out = {k: v for k, v in a.items() if k in ("place", "other", "state", "metric", "hour")}
    if a.get("start"):
        out["start_date"] = a["start"]
    if a.get("end"):
        out["end_date"] = a["end"]
    return name, out


def _arg_ok(got: dict, want: dict) -> bool:
    for k, v in want.items():
        g = got.get(k)
        if isinstance(v, int):
            try:
                if int(g) != v:
                    return False
            except (TypeError, ValueError):
                return False
        elif v.lower() not in str(g or "").lower():
            return False
    return True


async def run_one(pid: str, schema: str, prompt: str) -> dict:
    tools = TOOLS if schema == "typed" else [LEGACY_SCHEMA]
    msgs = [
        {"role": "system", "content": SYSTEM.format(today=TODAY.isoformat())},
        {"role": "user", "content": prompt},
    ]
    tok = ollama_client.use_provider(pid)
    t0 = time.perf_counter()
    try:
        out = await ollama_client.chat(msgs, tools=tools)
    except Exception as exc:  # noqa: BLE001
        out = {"error": type(exc).__name__, "tool_calls": []}
    finally:
        ollama_client.reset_provider(tok)
    ms = int((time.perf_counter() - t0) * 1000)
    calls = []
    for c in out.get("tool_calls") or []:
        if schema == "typed":
            name = c.get("name") or ""
            try:
                args = json.loads(c.get("arguments") or "{}")
            except ValueError:
                args = {}
            valid = to_data_args(name, c.get("arguments"))[1] is None
        else:
            name, args = _typed_from_legacy(c)
            valid = to_data_args("data", c.get("arguments"))[1] is None
        calls.append({"name": name, "args": args, "valid": valid})
    return {
        "ms": ms,
        "provider": out.get("provider"),
        "stripped": bool(out.get("tools_stripped")),
        "error": str(out.get("error") or "")[:80],
        "calls": calls,
    }


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--providers", default="gemini,groq")
    ap.add_argument("--schemas", default="typed,legacy")
    ap.add_argument("--sleep", type=float, default=4.5, help="seconds between calls (free-tier RPM)")
    ap.add_argument("--out", default="eval_tool_calls.json")
    ns = ap.parse_args()
    report: dict = {"date": TODAY.isoformat(), "runs": {}}
    for pid in [p.strip() for p in ns.providers.split(",") if p.strip()]:
        spec = registry.spec(pid)
        if not (spec and spec.keyed):
            print(f"{pid}: no key configured, skipped")
            continue
        for schema in [s.strip() for s in ns.schemas.split(",") if s.strip()]:
            rows = []
            score = {"tool": 0, "args": 0, "valid": 0, "n": 0, "parallel_ok": 0, "parallel_n": 0}
            for prompt, want, want_args in CASES:
                r = await run_one(pid, schema, prompt)
                got = {c["name"] for c in r["calls"]}
                tool_ok = got == want
                args_ok = tool_ok and all(
                    any(c["name"] == n and _arg_ok(c["args"], a) for c in r["calls"]) for n, a in want_args.items()
                )
                valid_ok = all(c["valid"] for c in r["calls"])
                score["n"] += 1
                score["tool"] += tool_ok
                score["args"] += args_ok
                score["valid"] += valid_ok
                if len(want) > 1:
                    score["parallel_n"] += 1
                    score["parallel_ok"] += tool_ok
                rows.append({"prompt": prompt, "want": sorted(want), **r, "tool_ok": tool_ok, "args_ok": args_ok})
                mark = "ok " if args_ok else ("~  " if tool_ok else "X  ")
                print(f"[{pid}/{schema}] {mark} {r['ms']:>5} ms  {prompt[:52]:<52} -> {sorted(got) or '-'}", flush=True)
                await asyncio.sleep(ns.sleep)
            model = spec.model
            report["runs"][f"{pid}/{schema}"] = {"model": model, "score": score, "rows": rows}
            n = score["n"] or 1
            ms = sorted(r["ms"] for r in rows)
            print(
                f"== {pid}:{model} {schema}: tool {score['tool']}/{n}  args {score['args']}/{n}  "
                f"valid {score['valid']}/{n}  parallel {score['parallel_ok']}/{score['parallel_n']}  "
                f"median {ms[len(ms) // 2]} ms",
                flush=True,
            )
    Path(ns.out).write_text(json.dumps(report, indent=1, ensure_ascii=False), encoding="utf-8")
    print(f"wrote {ns.out}")


if __name__ == "__main__":
    asyncio.run(main())

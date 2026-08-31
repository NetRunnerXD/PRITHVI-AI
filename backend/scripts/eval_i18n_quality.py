"""Live quality: same questions in several languages vs English, dash-null check, Reply-in wiring.

  cd backend
  python scripts/eval_i18n_quality.py
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.agents.facts import has_null_metrics, is_dash_soup  # noqa: E402
from app.agents.orchestrator import run_agent  # noqa: E402
from app.i18n.detect import has_script  # noqa: E402
from app.i18n.number_lock import NUM  # noqa: E402
from app.llm import ollama_client  # noqa: E402
from app.schemas.chat import ChatRequest  # noqa: E402
from app.services.location_svc import resolve_location  # noqa: E402

PROMPTS = [
    {
        "id": "howrah-weather",
        "place": "Howrah",
        "en": "What is the weather in Howrah today?",
        "hi": "हावड़ा में आज मौसम कैसा है?",
        "bn": "হাওড়ায় আজ আবহাওয়া কেমন?",
        "ta": "ஹவ்ராவில் இன்று வானிலை எப்படி?",
    },
    {
        "id": "haldia-aqi",
        "place": "Haldia",
        "en": "What is the AQI in Haldia?",
        "hi": "हल्दिया में AQI कितना है?",
        "bn": "হলদিয়ায় AQI কত?",
    },
    {
        "id": "nadia-rain",
        "place": "Nadia",
        "en": "How much rain in Nadia in the next 3 days?",
        "hi": "नदिया में अगले 3 दिन कितनी बारिश होगी?",
        "bn": "নদিয়ায় আগামী ৩ দিনে কত বৃষ্টি?",
        "te": "నదియాలో వచ్చే 3 రోజుల్లో ఎంత వర్షం?",
    },
]


async def ask(message: str, place: str, output_locale: str, locale_hint: str = "en") -> dict:
    loc = resolve_location(q=place)
    payload = ChatRequest(
        message=message,
        location=loc,
        output_locale=output_locale,
        locale_hint=locale_hint,
        stream=False,
    )
    final = None
    notices: list[str] = []
    async for ev in run_agent(payload):
        if ev.get("type") == "notice" and ev.get("message"):
            notices.append(str(ev["message"]))
        if ev.get("type") == "final":
            final = ev["message"]
    return {"final": final or {}, "notices": notices}


def score_pair(en_msg: dict, other_msg: dict, expect_locale: str) -> dict:
    en = en_msg.get("content_en") or en_msg.get("content") or ""
    other = other_msg.get("content") or ""
    other_en = other_msg.get("content_en") or ""
    loc = other_msg.get("locale")
    nums_en = set(NUM.findall(en))
    nums_ot = set(NUM.findall(other))
    nums_oe = set(NUM.findall(other_en))
    dash = has_null_metrics(other) or is_dash_soup(other)
    script_ok = expect_locale == "en" or has_script(other, expect_locale) or loc == "en"
    shared = nums_en & nums_oe
    reasons = []
    if loc != expect_locale:
        reasons.append(f"locale {loc}!={expect_locale}")
    if dash:
        reasons.append("null-dash metrics")
    if expect_locale != "en" and loc == expect_locale and not has_script(other, expect_locale):
        reasons.append("missing target script")
    if nums_en and not (nums_en & nums_ot) and loc != "en":
        reasons.append("no shared figures in translated body")
    if nums_en and not shared:
        reasons.append("English drafts diverged (content_en)")
    ok = not reasons
    return {
        "ok": ok,
        "reasons": reasons,
        "locale": loc,
        "engine": ((other_msg.get("translation") or {}).get("engine")),
        "nums_en": sorted(nums_en)[:12],
        "nums_other": sorted(nums_ot)[:12],
        "en_preview": en[:220],
        "other_preview": other[:220],
        "script_ok": script_ok,
    }


async def main() -> int:
    ok, detail = await ollama_client.ping()
    if not ok:
        print("Ollama down:", detail)
        return 2
    rows = []

    for case in PROMPTS:
        print("…", case["id"], "EN", flush=True)
        base = await ask(case["en"], case["place"], "en")
        base_msg = base["final"]
        rows.append(
            {
                "id": case["id"],
                "lang": "en",
                "ok": not has_null_metrics(base_msg.get("content") or "") and base_msg.get("locale") == "en",
                "locale": base_msg.get("locale"),
                "preview": (base_msg.get("content") or "")[:220],
            }
        )
        for lang, q in case.items():
            if lang in {"id", "place", "en"}:
                continue
            print("…", case["id"], lang, flush=True)
            got = await ask(q, case["place"], "auto")
            row = score_pair(base_msg, got["final"], lang)
            row["id"] = case["id"]
            row["lang"] = lang
            rows.append(row)
            print("  ", "OK" if row["ok"] else "FAIL", row.get("reasons"), flush=True)

    # Reply-in wiring: Hindi question, force EN / HI / AUTO
    hi_q = PROMPTS[0]["hi"]
    place = PROMPTS[0]["place"]
    print("… reply-in EN/HI/AUTO", flush=True)
    forced_en = await ask(hi_q, place, "en")
    forced_hi = await ask(hi_q, place, "hi")
    auto_hi = await ask(hi_q, place, "auto")
    wire = [
        {
            "id": "switch-en",
            "ok": forced_en["final"].get("locale") == "en"
            and not has_script(forced_en["final"].get("content") or "", "hi"),
            "locale": forced_en["final"].get("locale"),
            "preview": (forced_en["final"].get("content") or "")[:180],
        },
        {
            "id": "switch-hi",
            "ok": forced_hi["final"].get("locale") == "hi"
            and has_script(forced_hi["final"].get("content") or "", "hi")
            and not has_null_metrics(forced_hi["final"].get("content") or ""),
            "locale": forced_hi["final"].get("locale"),
            "preview": (forced_hi["final"].get("content") or "")[:180],
        },
        {
            "id": "switch-auto",
            "ok": auto_hi["final"].get("locale") == "hi"
            and has_script(auto_hi["final"].get("content") or "", "hi"),
            "locale": auto_hi["final"].get("locale"),
            "preview": (auto_hi["final"].get("content") or "")[:180],
        },
    ]
    for w in wire:
        print("  ", w["id"], "OK" if w["ok"] else "FAIL", w["locale"], flush=True)
    rows.extend(wire)

    fails = [r for r in rows if not r.get("ok")]
    print(json.dumps({"n": len(rows), "fail": len(fails), "rows": rows}, indent=2, ensure_ascii=False)[:12000])
    return 1 if fails else 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))

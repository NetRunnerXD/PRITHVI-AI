from __future__ import annotations

from pathlib import Path

KNOWLEDGE = Path(__file__).resolve().parent / "knowledge"

_TOPIC_FILES = {
    "irrigation": "irrigation_playbook.md",
    "sech": "irrigation_playbook.md",
    "pump": "irrigation_playbook.md",
    "crop": "kharif_rabi.md",
    "kharif": "kharif_rabi.md",
    "rabi": "kharif_rabi.md",
    "rice": "kharif_rabi.md",
    "intent": "advisor_intents.md",
    "nowcast": "advisor_intents.md",
    "window": "advisor_intents.md",
    "tool": "advisor_intents.md",
}


def retrieve(topic: str, locale: str = "en") -> dict:
    topic_l = (topic or "").lower()
    chosen: list[Path] = []
    for key, fname in _TOPIC_FILES.items():
        if key in topic_l:
            path = KNOWLEDGE / fname
            if path.exists() and path not in chosen:
                chosen.append(path)
    if not chosen:
        fallback = KNOWLEDGE / "advisor_intents.md"
        if fallback.exists():
            chosen = [fallback]
    body = "\n\n".join(f"## {p.stem}\n{p.read_text(encoding='utf-8')}" for p in chosen)[:4000]
    return {
        "topic": topic,
        "locale": locale,
        "source": "bundled-rag",
        "text": body,
        "note": "AIKosh KCC ingest activates when AIKOSH_API_KEY is set.",
    }

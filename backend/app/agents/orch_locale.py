from __future__ import annotations

import re
from typing import Any

from app.agents.binder import looks_like_dump
from app.agents.facts import has_null_metrics, is_dash_soup
from app.i18n.detect import has_script
from app.i18n.mt import inbound as mt_inbound, outbound as mt_outbound
from app.i18n.mt import MTResult
from app.i18n.number_lock import NUM
from app.llm import ollama_client

async def _english_history(history: list[Any] | None) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    for h in (history or [])[-6:]:
        role = h.role if getattr(h, "role", None) in {"user", "assistant"} else "user"
        ready = getattr(h, "content_en", None)
        raw = getattr(h, "content", None) or ""
        if ready:
            content = ready
        else:
            pack = await mt_inbound(raw, getattr(h, "locale", None))
            content = pack.text
        out.append({"role": role, "content": content})
    return out


def _mt_kept_numbers(en: str, translated: str) -> bool:
    """True when Indic text still carries the English draft's significant figures."""
    if is_dash_soup(translated) or "⟦" in (translated or "") or "⟧" in (translated or ""):
        return False
    skip = {str(i) for i in range(0, 16)} | {"2024", "2025", "2026", "2027", "2028"}
    need = {n for n in NUM.findall(en or "") if n not in skip}
    if not need:
        return True
    have = set(NUM.findall(translated or ""))
    return bool(need & have)


_LANG_NAME = {
    "hi": "Hindi (Devanagari script)",
    "bn": "Bengali (Bangla script)",
    "mr": "Marathi (Devanagari script)",
    "ne": "Nepali (Devanagari script)",
    "gu": "Gujarati script",
    "pa": "Punjabi (Gurmukhi script)",
    "or": "Odia script",
    "ta": "Tamil script",
    "te": "Telugu script",
    "kn": "Kannada script",
    "ml": "Malayalam script",
    "as": "Assamese (Bengali-Assamese script)",
    "ur": "Urdu (Perso-Arabic script)",
    "sd": "Sindhi",
    "sa": "Sanskrit (Devanagari script)",
    "mai": "Maithili (Devanagari script)",
    "kok": "Konkani",
    "mni": "Manipuri",
    "brx": "Bodo (Devanagari script)",
    "doi": "Dogri (Devanagari script)",
    "sat": "Santali",
    "ks": "Kashmiri",
}


def _usable_translation(en: str, pack: MTResult | None, tgt: str) -> bool:
    if pack is None or not pack.ok or not (pack.text or "").strip():
        return False
    body = pack.text
    if looks_like_dump(body) or is_dash_soup(body) or has_null_metrics(body):
        return False
    if "⟦" in body or "⟧" in body:
        return False
    if not has_script(body, tgt):
        return False
    return _mt_kept_numbers(en, body)


async def _llm_translate(text: str, tgt: str) -> MTResult:
    """Whole-document translation via the active chat model when Google/MyMemory fail."""
    blob = (text or "").strip()
    if not blob:
        return MTResult(text=text, src="en", tgt=tgt, engine="llm", ok=False)
    name = _LANG_NAME.get(tgt, tgt)
    messages = [
        {
            "role": "system",
            "content": (
                f"Translate the weather answer into {name}. "
                "Keep every digit, unit (°C, mm, %, km/h), ISO date, and acronym "
                "(IMD, CPCB, AQI, CAP, Open-Meteo, NAQI) exactly as written. "
                "Do not add, drop, or round figures. Do not transliterate into Latin. "
                "Output only the translation — no quotes, no preface."
            ),
        },
        {"role": "user", "content": blob},
    ]
    try:
        resp = await ollama_client.chat(messages)
        body = (resp.get("content") or "").strip()
    except Exception:
        return MTResult(text=text, src="en", tgt=tgt, engine="llm", ok=False)
    if body.startswith("```"):
        body = re.sub(r"^```[a-zA-Z0-9_-]*\n?", "", body)
        body = re.sub(r"\n?```$", "", body).strip()
    if not body or body == blob:
        return MTResult(text=text, src="en", tgt=tgt, engine="llm", ok=False)
    if not has_script(body, tgt):
        return MTResult(text=text, src="en", tgt=tgt, engine="llm-no-script", ok=False)
    if not _mt_kept_numbers(blob, body):
        return MTResult(text=text, src="en", tgt=tgt, engine="llm-lost-numbers", ok=False)
    return MTResult(text=body, src="en", tgt=tgt, engine="llm", ok=True)


async def _localize_validated(content_en: str, out_locale: str, *, native: bool = False):
    """After English validation, translate the whole reply. Never splice templates."""
    if out_locale == "en" or not (content_en or "").strip():
        return content_en, None, "llm-en"
    if native and has_script(content_en, out_locale):
        ident = MTResult(text=content_en, src=out_locale, tgt=out_locale, engine="gemini-native", ok=True)
        return content_en, ident, "gemini-native"
    outbound = await mt_outbound(content_en, out_locale)
    if _usable_translation(content_en, outbound, out_locale):
        return outbound.text, outbound, f"llm-en+{outbound.engine}"
    llm_out = await _llm_translate(content_en, out_locale)
    if _usable_translation(content_en, llm_out, out_locale):
        return llm_out.text, llm_out, f"llm-en+{llm_out.engine}"
    return content_en, outbound or llm_out, "en-fallback"



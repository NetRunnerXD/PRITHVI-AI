"""Gemini 2.0 Flash native languages (Firebase / Vertex lists).

Core 40 on all Gemini models, plus 2.0 Flash extras used in this app.
Do not bypass MT for weak Eighth-Schedule codes (sat, brx, doi, ks, sa, mni, kok, mai).
"""

from __future__ import annotations

from app.i18n.detect import normalize_lang

# All Gemini models.
_CORE = {
    "ar", "bn", "bg", "zh", "hr", "cs", "da", "nl", "en", "et", "fi", "fr", "de", "el",
    "he", "iw", "hi", "hu", "id", "it", "ja", "ko", "lv", "lt", "no", "pl", "pt", "ro",
    "ru", "sr", "sk", "sl", "es", "sw", "sv", "th", "tr", "uk", "vi",
}

# Gemini 2.0 Flash extras (subset we actually detect).
_FLASH_EXTRA = {
    "af", "am", "as", "az", "be", "bs", "ca", "cy", "eu", "fa", "fil", "ga", "gl",
    "gu", "ha", "hy", "is", "kn", "km", "ku", "lo", "mk", "ml", "mn", "mr", "ms",
    "mt", "my", "ne", "or", "pa", "ps", "sd", "si", "so", "sq", "ta", "te", "ur",
    "uz", "zu",
}

GEMINI_NATIVE = _CORE | _FLASH_EXTRA

# Eighth Schedule codes Gemini does not list as native.
GEMINI_WEAK_INDIC = {"sat", "brx", "doi", "ks", "sa", "mni", "kok", "mai"}


def gemini_native(lang: str | None) -> bool:
    code = normalize_lang(lang) or (lang or "").strip().lower()
    if not code or code in GEMINI_WEAK_INDIC:
        return False
    if code == "iw":
        code = "he"
    return code in GEMINI_NATIVE

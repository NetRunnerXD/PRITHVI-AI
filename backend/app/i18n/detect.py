from __future__ import annotations

import re

try:
    from langdetect import detect as _ld
except Exception:  # pragma: no cover
    _ld = None

# ISO 639-1 → script. Devanagari is shared (hi/mr/ne); Bengali script also covers Assamese.
_SCRIPTS: list[tuple[str, re.Pattern[str]]] = [
    ("bn", re.compile(r"[\u0980-\u09FF]")),
    ("hi", re.compile(r"[\u0900-\u097F]")),
    ("pa", re.compile(r"[\u0A00-\u0A7F]")),
    ("gu", re.compile(r"[\u0A80-\u0AFF]")),
    ("or", re.compile(r"[\u0B00-\u0B7F]")),
    ("ta", re.compile(r"[\u0B80-\u0BFF]")),
    ("te", re.compile(r"[\u0C00-\u0C7F]")),
    ("kn", re.compile(r"[\u0C80-\u0CFF]")),
    ("ml", re.compile(r"[\u0D00-\u0D7F]")),
    ("si", re.compile(r"[\u0D80-\u0DFF]")),
    ("th", re.compile(r"[\u0E00-\u0E7F]")),
    ("lo", re.compile(r"[\u0E80-\u0EFF]")),
    ("my", re.compile(r"[\u1000-\u109F]")),
    ("ka", re.compile(r"[\u10A0-\u10FF]")),
    ("am", re.compile(r"[\u1200-\u137F]")),
    ("el", re.compile(r"[\u0370-\u03FF]")),
    ("ru", re.compile(r"[\u0400-\u04FF]")),
    ("he", re.compile(r"[\u0590-\u05FF]")),
    ("ar", re.compile(r"[\u0600-\u06FF]")),
    ("ko", re.compile(r"[\uAC00-\uD7AF]")),
    ("ja", re.compile(r"[\u3040-\u30FF]")),
    ("zh", re.compile(r"[\u4E00-\u9FFF]")),
]

_SCRIPT_BY_LANG = {code: pat for code, pat in _SCRIPTS}

# Reply UI is en/hi/bn; script cousins share the same has_script check.
_SCRIPT_ALIAS = {
    "mr": "hi",
    "ne": "hi",
    "as": "bn",
    "ur": "ar",
    "fa": "ar",
    "zh-cn": "zh",
    "zh-tw": "zh",
}

# Eighth Schedule + English. Auto replies in the detected code when it is here.
SCHEDULED_22 = {
    "as", "bn", "brx", "doi", "gu", "hi", "kn", "ks", "kok", "mai",
    "ml", "mni", "mr", "ne", "or", "pa", "sa", "sat", "sd", "ta", "te", "ur",
}

_LD_MAP = {
    "bn": "bn",
    "hi": "hi",
    "mr": "mr",
    "ne": "ne",
    "en": "en",
    "ta": "ta",
    "te": "te",
    "kn": "kn",
    "ml": "ml",
    "gu": "gu",
    "pa": "pa",
    "or": "or",
    "ur": "ur",
    "as": "as",
    "brx": "brx",
    "doi": "doi",
    "kok": "kok",
    "mai": "mai",
    "mni": "mni",
    "sa": "sa",
    "sat": "sat",
    "sd": "sd",
    "ks": "ks",
    "auto": "auto",
    "fr": "fr",
    "es": "es",
    "de": "de",
    "it": "it",
    "pt": "pt",
    "ru": "ru",
    "ar": "ar",
    "fa": "fa",
    "tr": "tr",
    "id": "id",
    "vi": "vi",
    "th": "th",
    "ja": "ja",
    "ko": "ko",
    "zh-cn": "zh",
    "zh-tw": "zh",
    "nl": "nl",
    "pl": "pl",
    "uk": "uk",
    "ro": "ro",
    "sv": "sv",
    "fi": "fi",
    "hu": "hu",
    "el": "el",
    "he": "he",
    "si": "si",
    "my": "my",
}


def normalize_lang(code: str | None) -> str | None:
    if not code:
        return None
    c = code.strip().lower().replace("_", "-")
    if c in _LD_MAP:
        return _LD_MAP[c]
    if c.startswith("zh"):
        return "zh"
    if c.startswith("bn"):
        return "bn"
    base = c.split("-")[0]
    return _LD_MAP.get(base, base if len(base) == 2 else None)


def script_of(text: str) -> str | None:
    blob = text or ""
    for code, pat in _SCRIPTS:
        if pat.search(blob):
            return code
    return None


def detect_lang(text: str, hint: str | None = None) -> str:
    """Detect the language of user text. Script wins; hint is last resort."""
    blob = text or ""
    script = script_of(blob)
    if script == "hi" and _ld:
        try:
            guessed = normalize_lang(_ld(blob))
            if guessed in {"hi", "mr", "ne"}:
                return guessed
        except Exception:
            pass
    if script:
        return script
    if _ld and len(blob.strip()) >= 10:
        try:
            guessed = normalize_lang(_ld(blob))
            if guessed:
                return guessed
        except Exception:
            pass
    hinted = normalize_lang(hint)
    if hinted:
        return hinted
    return "en"


def has_script(text: str, locale: str) -> bool:
    key = _SCRIPT_ALIAS.get((locale or "").lower(), (locale or "").lower())
    if key in {"en", ""}:
        return True
    pat = _SCRIPT_BY_LANG.get(key)
    if pat is None:
        return True
    return bool(pat.search(text or ""))


def pick_output_locale(
    *,
    output_locale: str | None,
    locale_hint: str | None,
    detected: str,
) -> str:
    """Reply language from the Chat Reply-in control.

    auto / empty → language of the question.
    en / hi / bn / … → that language, even if the question was typed in another.
    locale_hint is only used when output_locale is missing.
    """
    raw_out = (output_locale or "").strip().lower()
    detected_n = normalize_lang(detected) or "en"
    if raw_out in {"auto", ""}:
        if raw_out == "" and locale_hint:
            hinted = normalize_lang(locale_hint)
            if hinted:
                return hinted
        return detected_n
    explicit = normalize_lang(output_locale)
    return explicit or detected_n

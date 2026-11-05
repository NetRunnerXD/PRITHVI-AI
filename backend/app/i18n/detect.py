from __future__ import annotations

import re

try:
    from langdetect import detect as _ld
except Exception:  # pragma: no cover
    _ld = None

# ISO 639-1 → script. Devanagari is shared (hi/mr/ne); Bengali script also covers Assamese.
_SCRIPTS: list[tuple[str, re.Pattern[str]]] = [
    # Ol Chiki (Santali) and Meetei Mayek (Manipuri) are unique scripts: check first.
    ("sat", re.compile(r"[\u1C50-\u1C7F]")),
    ("mni", re.compile(r"[\uABC0-\uABFF\uAAE0-\uAAFF]")),
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
    "kok": "hi",
    "mai": "hi",
    "sa": "hi",
    "doi": "hi",
    "brx": "hi",
    "as": "bn",
    "ur": "ar",
    "sd": "ar",
    "ks": "ar",
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
    "gom": "kok",
    "od": "or",
    "mni-mtei": "mni",
    "hinglish": "hinglish",
    "hi-latn": "hinglish",
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


# Languages that share a script. When the user picked one of these, trust it.
SCRIPT_FAMILY: dict[str, set[str]] = {
    "hi": {"hi", "mr", "ne", "kok", "mai", "sa", "doi", "brx"},
    "bn": {"bn", "as", "mni"},
    "ar": {"ur", "sd", "ks"},
    "sat": {"sat"},
    "mni": {"mni"},
}

_URDU_MARKS = re.compile(r"[\u06BA\u06BE\u06C1\u06D2\u0679\u0688\u0691]")  # ں ھ ہ ے ٹ ڈ ڑ
_SINDHI_MARKS = re.compile(r"[\u0684\u0683\u0687\u067B\u0680\u067A\u067D\u06A6\u06BB\u06B1\u068A\u068F\u068D]")
_KASHMIRI_MARKS = re.compile(r"[\u0672\u0673\u0620\u06C4\u06C6\u065F]")

# Common Hindi words written in Latin script (Hinglish chat).
_HINGLISH = {
    "hai", "hain", "kya", "kyaa", "kal", "aaj", "parso", "barish", "baarish", "barsaat", "mausam", "hoga",
    "hogi", "honge", "nahi", "nahin", "mein", "me", "ka", "ki", "ke", "ko", "se", "kaisa", "kaisi", "kitna",
    "kitni", "kab", "garmi", "thand", "thandi", "hawa", "bataiye", "batao", "bata", "yahan", "wahan", "abhi",
    "bahut", "zyada", "jyada", "kam", "chalega", "chahiye", "karna", "karu", "karun", "jaana", "jana",
    "baadal", "badal", "toofan", "tufan", "aandhi", "dhoop", "dhup", "boond", "paani", "pani", "khet",
    "fasal", "sinchai", "subah", "shaam", "raat", "din", "agle", "agla", "ghante", "ghanta", "mere", "mera",
    "meri", "hum", "aap", "tum", "kaise", "kaun", "kahan", "kyun", "lagega", "lag", "rahi", "raha", "rahe",
    "gaya", "gayi", "padegi", "padega", "hoti", "hota", "bhi", "aur", "ya", "toh", "to", "kuch", "sab",
    "accha", "achha", "theek", "thik", "bijli", "garaj", "chhata", "chata", "baahar", "bahar", "nikalna",
}
_HINGLISH_STRONG = {
    "hai", "kya", "barish", "baarish", "mausam", "hoga", "hogi", "nahi", "nahin", "kaisa", "kitna", "aaj",
    "kal", "garmi", "thand", "bataiye", "batao", "chahiye", "hawa", "toofan", "aandhi", "abhi", "ghante",
}


def is_hinglish(text: str) -> bool:
    """Romanised Hindi (Latin script). Needs 2+ Hindi words incl. one strong cue."""
    blob = (text or "").strip()
    if not blob or script_of(blob):
        return False
    words = re.findall(r"[a-z]+", blob.lower())
    if len(words) < 2:
        return False
    hits = [w for w in words if w in _HINGLISH]
    if len(hits) < 2 or not any(w in _HINGLISH_STRONG for w in hits):
        return False
    return len(hits) / len(words) >= 0.3


def _arabic_lang(blob: str, hinted: str | None) -> str:
    if hinted in {"ur", "sd", "ks"}:
        return hinted
    if _KASHMIRI_MARKS.search(blob):
        return "ks"
    if _SINDHI_MARKS.search(blob):
        return "sd"
    if _URDU_MARKS.search(blob):
        return "ur"
    return "ur"


def detect_lang(text: str, hint: str | None = None, picked: str | None = None) -> str:
    """Detect the language of user text.

    Script wins. Inside a shared script (Devanagari, Bengali, Perso-Arabic) the language the
    user explicitly picked wins over guessing. `hint` (UI locale) is only a last resort.
    """
    blob = text or ""
    hinted = normalize_lang(hint)
    chosen = normalize_lang(picked)
    script = script_of(blob)
    if script and chosen and chosen in SCRIPT_FAMILY.get(script, ()):
        return chosen
    if script == "ar":
        return _arabic_lang(blob, chosen)
    if script == "hi" and _ld:
        try:
            guessed = normalize_lang(_ld(blob))
            if guessed in {"hi", "mr", "ne"}:
                return guessed
        except Exception:
            pass
    if script == "bn" and re.search("[\u09F0\u09F1]", blob):
        return "as"  # ৰ ৱ are Assamese-only letters
    if script:
        return script
    if chosen == "hinglish" or is_hinglish(blob):
        return "hinglish"
    if _ld and len(blob.strip()) >= 10:
        try:
            guessed = normalize_lang(_ld(blob))
            if guessed:
                return guessed
        except Exception:
            pass
    if hinted:
        return hinted
    return "en"


def has_script(text: str, locale: str) -> bool:
    key = _SCRIPT_ALIAS.get((locale or "").lower(), (locale or "").lower())
    if key in {"en", "", "hinglish"}:
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

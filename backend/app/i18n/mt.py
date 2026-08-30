"""Online MT layer for the Advisor.

Inbound: any language → English for intent routing and the tool-calling LLM.
Outbound: English draft → the reply language. Numbers and source acronyms are
locked so Google/MyMemory cannot invent or drop figures.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from typing import Any

from app import cache
from app.config import get_settings
from app.i18n.detect import detect_lang, has_script, normalize_lang, script_of
from app.i18n.number_lock import ISO_DATE
from app.providers import http as http_provider

GTX_URL = "https://translate.googleapis.com/translate_a/single"
MYMEMORY_URL = "https://api.mymemory.translated.net/get"

# Google's unofficial gtx client is the primary no-key engine; MyMemory is fallback.
_GTX_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
}

_GOOGLE_CODE = {
    "zh": "zh-CN",
    "he": "iw",
    "jw": "jw",
    "or": "or",
    "pa": "pa",
    "as": "as",
    "sa": "sa",
    "sd": "sd",
    "ur": "ur",
    "mni": "mni",
    "mai": "mai",
    "kok": "gom",
    "ks": "ks",
    "brx": "brx",
    "doi": "doi",
    "sat": "sat",
}

# Longest first so NAQI is not split by AQI.
_PROTECT_TERMS = [
    "Open-Meteo",
    "OpenMeteo",
    "data.gov.in",
    "Agmarknet",
    "INCOIS",
    "ITEWS",
    "GloFAS",
    "CPCB",
    "USGS",
    "NAQI",
    "IMD",
    "AQI",
    "CAP",
    "ET₀",
    "ET0",
    "INR",
]

# Skip digits already inside ⟦0⟧ so we do not re-mask tokens.
_NUM = re.compile(r"(?<![A-Za-z⟦0-9.])\d+(?:\.\d+)?(?![A-Za-z⟧])")
_TERM_RES = [
    (term, re.compile(rf"(?<![A-Za-z]){re.escape(term)}(?![A-Za-z])", re.I))
    for term in _PROTECT_TERMS
]


@dataclass
class MTResult:
    text: str
    src: str
    tgt: str
    engine: str
    ok: bool

    def as_dict(self) -> dict[str, Any]:
        return {"src": self.src, "tgt": self.tgt, "engine": self.engine, "ok": self.ok}


def _identity(text: str, src: str, tgt: str) -> MTResult:
    return MTResult(text=text, src=src, tgt=tgt, engine="identity", ok=True)


def _tok(i: int) -> str:
    # Google transliterates Latin letter tokens (XLT0XLT → एक्सएलटी…).
    # Corner brackets survive hi/bn unchanged.
    return f"⟦{i}⟧"


def protect(text: str) -> tuple[str, list[str]]:
    """Replace numbers, ISO dates, and source acronyms with inert tokens."""
    held: list[str] = []
    out = text or ""

    def stash(raw: str) -> str:
        held.append(raw)
        return _tok(len(held) - 1)

    out = ISO_DATE.sub(lambda m: stash(m.group(0)), out)
    for _term, pat in _TERM_RES:
        out = pat.sub(lambda m: stash(m.group(0)), out)
    out = _NUM.sub(lambda m: stash(m.group(0)), out)
    return out, held


def _token_forms(i: int) -> list[str]:
    fw = "".join(chr(0xFF10 + int(c)) if c.isdigit() else c for c in str(i))
    return [
        f"⟦{i}⟧",
        f"⟦ {i} ⟧",
        f"[[{i}]]",
        f"[{i}]",
        f"[ {i} ]",
        f"【{i}】",
        f"({i})",
        f"（{i}）",
        f"{{{i}}}",
        f"⟦{fw}⟧",
    ]


def restore(text: str, held: list[str]) -> str:
    out = text or ""
    for i, val in enumerate(held):
        for pat in _token_forms(i):
            if pat in out:
                out = out.replace(pat, val)

    def _by_index(m: re.Match[str]) -> str:
        idx = int(m.group(1))
        if 0 <= idx < len(held):
            return held[idx]
        return m.group(0)

    out = re.sub(r"[⟦\[]\s*(\d+)\s*[⟧\]]", _by_index, out)
    out = re.sub(r"⟦\s*(\d+)", _by_index, out)
    out = re.sub(r"(\d+)\s*⟧", _by_index, out)
    return out


def held_missing(text: str, held: list[str]) -> list[str]:
    blob = text or ""
    return [v for v in held if v and v not in blob]


def _chunks(text: str, limit: int = 900) -> list[str]:
    if len(text) <= limit:
        return [text]
    parts: list[str] = []
    buf = ""
    for para in text.split("\n"):
        if len(buf) + len(para) + 1 <= limit:
            buf = f"{buf}\n{para}" if buf else para
            continue
        if buf:
            parts.append(buf)
        if len(para) <= limit:
            buf = para
            continue
        for i in range(0, len(para), limit):
            parts.append(para[i : i + limit])
        buf = ""
    if buf:
        parts.append(buf)
    return parts


def _google_code(code: str) -> str:
    c = (code or "auto").strip()
    if c in {"", "auto"}:
        return "auto"
    n = normalize_lang(c) or c
    return _GOOGLE_CODE.get(n, n)


def _parse_gtx(data: Any) -> tuple[str, str | None]:
    if not isinstance(data, list) or not data:
        return "", None
    bits: list[str] = []
    first = data[0]
    if isinstance(first, list):
        for row in first:
            if isinstance(row, list) and row and isinstance(row[0], str):
                bits.append(row[0])
    detected = data[2] if len(data) > 2 and isinstance(data[2], str) else None
    return "".join(bits).strip(), normalize_lang(detected)


async def _gtx(text: str, src: str, tgt: str) -> MTResult | None:
    client = http_provider.client()
    sl = _google_code(src)
    tl = _google_code(tgt)
    try:
        resp = await client.post(
            GTX_URL,
            params={"client": "gtx", "sl": sl, "tl": tl, "dt": "t"},
            data={"q": text},
            headers={**_GTX_HEADERS, "Content-Type": "application/x-www-form-urlencoded"},
            timeout=15.0,
        )
        if resp.status_code != 200:
            return None
        body, detected = _parse_gtx(resp.json())
        if not body:
            return None
        return MTResult(text=body, src=detected or (normalize_lang(src) or "auto"), tgt=tgt, engine="google-gtx", ok=True)
    except Exception:
        return None


async def _mymemory(text: str, src: str, tgt: str) -> MTResult | None:
    client = http_provider.client()
    sl = normalize_lang(src) or "Autodetect"
    if sl in {"auto", ""}:
        sl = "Autodetect"
    tl = normalize_lang(tgt) or tgt
    out_bits: list[str] = []
    try:
        for chunk in _chunks(text, 450):
            resp = await client.get(
                MYMEMORY_URL,
                params={"q": chunk, "langpair": f"{sl}|{tl}"},
                timeout=15.0,
            )
            if resp.status_code != 200:
                return None
            data = resp.json()
            piece = ((data or {}).get("responseData") or {}).get("translatedText") or ""
            status = (data or {}).get("responseStatus")
            if status not in (200, "200") or not piece:
                return None
            if piece.lower().startswith("query length limit"):
                return None
            out_bits.append(piece)
        body = "\n".join(out_bits).strip()
        if not body:
            return None
        return MTResult(text=body, src=normalize_lang(src) or "auto", tgt=tgt, engine="mymemory", ok=True)
    except Exception:
        return None


def _cache_key(src: str, tgt: str, text: str) -> str:
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()[:20]
    return f"mt:{src}:{tgt}:{digest}"


async def translate(text: str, src: str, tgt: str) -> MTResult:
    """Translate `text` from `src` (or auto) to `tgt`. Identity if src == tgt."""
    blob = text or ""
    tgt_n = normalize_lang(tgt) or tgt or "en"
    src_n = normalize_lang(src) or src or "auto"
    if not blob.strip():
        return _identity(blob, src_n, tgt_n)
    if src_n == tgt_n:
        return _identity(blob, src_n, tgt_n)

    settings = get_settings()
    if not settings.translate_enabled:
        return MTResult(text=blob, src=src_n, tgt=tgt_n, engine="disabled", ok=False)

    ck = _cache_key(src_n, tgt_n, blob)
    hit = cache.get(ck)
    if isinstance(hit, dict) and hit.get("text"):
        return MTResult(
            text=hit["text"],
            src=hit.get("src") or src_n,
            tgt=tgt_n,
            engine=hit.get("engine") or "cache",
            ok=True,
        )

    masked, held = protect(blob)
    pieces = _chunks(masked, 900)
    last_err = "none"
    for factory in (_gtx, _mymemory):
        translated: list[str] = []
        detected = src_n
        engine = "none"
        failed = False
        for piece in pieces:
            pack = await factory(piece, src_n if src_n != "auto" else "auto", tgt_n)
            if pack is None or not pack.text:
                failed = True
                last_err = factory.__name__
                break
            translated.append(pack.text)
            detected = pack.src or detected
            engine = pack.engine
        if failed:
            continue
        body = restore("\n".join(translated), held)
        if "⟦" in body or "⟧" in body:
            last_err = f"{engine}-leaked-lock"
            continue
        lost = held_missing(body, held)
        if lost:
            last_err = f"{engine}-lost-lock"
            continue
        if tgt_n != "en" and not _plausible(blob, body, tgt_n):
            last_err = f"{engine}-implausible"
            continue
        result = MTResult(text=body, src=detected or src_n, tgt=tgt_n, engine=engine, ok=True)
        cache.set(ck, result.as_dict() | {"text": result.text}, ttl_s=6 * 3600)
        return result

    return MTResult(text=blob, src=src_n, tgt=tgt_n, engine=f"failed:{last_err}", ok=False)


def _plausible(original: str, translated: str, tgt: str) -> bool:
    if not (translated or "").strip():
        return False
    if tgt != "en" and translated.strip() == original.strip() and script_of(original) is None:
        # English source left unchanged when a non-English target was requested
        return False
    if not has_script(translated, tgt):
        return False
    return True


async def inbound(text: str, hint: str | None = None) -> MTResult:
    """User text (any language) → English for the LLM."""
    blob = text or ""
    detected = detect_lang(blob, hint)
    if not blob.strip() or detected == "en":
        return _identity(blob, detected or "en", "en")
    result = await translate(blob, "auto", "en")
    if result.ok:
        result.src = result.src if result.src not in {"auto", ""} else detected
        return result
    return MTResult(text=blob, src=detected, tgt="en", engine=result.engine, ok=False)


async def outbound(text: str, tgt: str, src: str = "en") -> MTResult:
    """English LLM draft → reply language."""
    blob = text or ""
    tgt_n = normalize_lang(tgt) or tgt or "en"
    if tgt_n == "en" or not blob.strip():
        return _identity(blob, "en", tgt_n)
    result = await translate(blob, src or "en", tgt_n)
    if result.ok and has_script(result.text, tgt_n):
        return result
    return MTResult(text=blob, src="en", tgt=tgt_n, engine=result.engine, ok=False)

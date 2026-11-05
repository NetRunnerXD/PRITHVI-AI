"""MT layer for the Advisor.

Inbound: any language → English for intent routing and the tool-calling LLM.
Outbound: English draft → the reply language. Numbers and source acronyms are
locked so a translator cannot invent or drop figures.

When MT_SIDECAR_URL is set, English ↔ the 22 scheduled languages go to the
IndicTrans2 distilled sidecar first. Google gtx, then MyMemory, still run when
that process is unset, down, or rejects a piece. The API process never loads
the weights.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import re
from dataclasses import dataclass
from typing import Any

import httpx

from app import cache
from app.config import get_settings
from app.i18n.detect import SCHEDULED_22, detect_lang, has_script, normalize_lang, script_of
from app.i18n.number_lock import ISO_DATE
from app.providers import http as http_provider

GTX_URL = "https://translate.googleapis.com/translate_a/single"
# Same unofficial Google stack. translate.googleapis.com/…/single?client=gtx is
# frequently 429; clients5 dict-chrome-ex still serves the same translations.
GTX_CLIENTS5_URL = "https://clients5.google.com/translate_a/t"
GTX_T_URL = "https://translate.googleapis.com/translate_a/t"
MYMEMORY_URL = "https://api.mymemory.translated.net/get"

# Google GET URLs blow past ~2k once q is percent-encoded; POST for anything longer.
_GTX_GET_MAX = 450

# Google's unofficial gtx client is the primary no-key engine; MyMemory is fallback.
_GTX_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9,hi;q=0.8,bn;q=0.7",
    "Referer": "https://translate.google.com/",
}

# Prefer the endpoint that still returns 200 from this network; keep classic gtx as well.
_GTX_ENDPOINTS: list[tuple[str, dict[str, str]]] = [
    (GTX_CLIENTS5_URL, {"client": "dict-chrome-ex"}),
    (GTX_URL, {"client": "gtx", "dt": "t", "ie": "UTF-8", "oe": "UTF-8"}),
    (GTX_T_URL, {"client": "gtx", "ie": "UTF-8", "oe": "UTF-8"}),
]

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
    # Google serves Manipuri only as Meetei Mayek ("mni" → HTTP 400).
    "mni": "mni-Mtei",
    "mai": "mai",
    "kok": "gom",
    "doi": "doi",
    "sat": "sat",
    # Romanised Hindi in: Google auto-detects it as hi and translates well.
    "hinglish": "auto",
}

# Google has no Bodo or Kashmiri (both return HTTP 400; MyMemory output is not the
# language). Replies route through the closest widely read language in the same script.
VIA = {"brx": "hi", "ks": "ur"}

# MyMemory returns another language for these (tested): never use it as a fallback.
_NO_MYMEMORY = {"brx", "ks", "mni", "sat", "doi", "kok", "mai", "sa", "hinglish"}

# IndicTrans2 Flores tags. One side of a sidecar pair is always English.
# Manipuri is Meitei Mayek: has_script("mni") checks that script, not Bengali.
# The toolkit transliterates sat_Olck through Odia and mni_Mtei through
# Devanagari, so those two replies fail has_script and stay on Google.
_FLORES = {
    "as": "asm_Beng",
    "bn": "ben_Beng",
    "brx": "brx_Deva",
    "doi": "doi_Deva",
    "en": "eng_Latn",
    "gu": "guj_Gujr",
    "hi": "hin_Deva",
    "kn": "kan_Knda",
    "ks": "kas_Arab",
    "kok": "gom_Deva",
    "mai": "mai_Deva",
    "ml": "mal_Mlym",
    "mni": "mni_Mtei",
    "mr": "mar_Deva",
    "ne": "npi_Deva",
    "or": "ory_Orya",
    "pa": "pan_Guru",
    "sa": "san_Deva",
    "sat": "sat_Olck",
    "sd": "snd_Arab",
    "ta": "tam_Taml",
    "te": "tel_Telu",
    "ur": "urd_Arab",
}

_SIDECAR_BUDGET_S = 20.0
_SENTENCE_CAP = 400
_LOCK_RE = re.compile(r"⟦(\d+)⟧")

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
    """Accept classic nested arrays, dict-chrome-ex [\"text\"], and dj=1 objects."""
    if isinstance(data, str):
        return data.strip(), None
    if isinstance(data, dict):
        sents = data.get("sentences") or []
        bits = [s.get("trans") or "" for s in sents if isinstance(s, dict)]
        src = data.get("src")
        return "".join(bits).strip(), normalize_lang(src) if isinstance(src, str) else None
    if not isinstance(data, list) or not data:
        return "", None
    first = data[0]
    if isinstance(first, str):
        extra = data[1] if len(data) > 1 and isinstance(data[1], str) and len(data[1]) <= 8 else None
        return first.strip(), normalize_lang(extra) if extra else None
    if (
        isinstance(first, list)
        and len(first) == 2
        and all(isinstance(x, str) for x in first)
        and len(first[1]) <= 8
    ):
        # clients5 dict-chrome-ex with sl=auto: [["translation", "detected_lang"]]
        return first[0].strip(), normalize_lang(first[1])
    bits: list[str] = []
    if isinstance(first, list):
        for row in first:
            if isinstance(row, str):
                bits.append(row)
            elif isinstance(row, list) and row and isinstance(row[0], str):
                bits.append(row[0])
    detected = data[2] if len(data) > 2 and isinstance(data[2], str) else None
    return "".join(bits).strip(), normalize_lang(detected)


def _gtx_body(resp: Any) -> tuple[str, str | None]:
    try:
        data = resp.json()
    except Exception:
        raw = (getattr(resp, "text", None) or "").strip()
        if not raw:
            return "", None
        try:
            data = json.loads(raw)
        except Exception:
            return "", None
    return _parse_gtx(data)


async def _gtx_hit(client: Any, url: str, base: dict[str, str], text: str, *, use_get: bool) -> Any | None:
    params = dict(base)
    headers = dict(_GTX_HEADERS)
    try:
        if use_get:
            return await client.get(url, params={**params, "q": text}, headers=headers, timeout=15.0)
        headers = {**headers, "Content-Type": "application/x-www-form-urlencoded"}
        return await client.post(url, params=params, data={"q": text}, headers=headers, timeout=20.0)
    except Exception:
        return None


async def _gtx(text: str, src: str, tgt: str) -> MTResult | None:
    client = http_provider.client()
    sl = _google_code(src)
    tl = _google_code(tgt)
    use_get = len(text) <= _GTX_GET_MAX
    last_status = "none"
    for url, extra in _GTX_ENDPOINTS:
        params = {"sl": sl, "tl": tl, **extra}
        methods = (True, False) if use_get else (False,)
        for get in methods:
            resp = await _gtx_hit(client, url, params, text, use_get=get)
            if resp is None:
                last_status = "exc"
                continue
            if resp.status_code == 429:
                last_status = "429"
                await asyncio.sleep(0.7)
                resp = await _gtx_hit(client, url, params, text, use_get=get)
                if resp is None or resp.status_code == 429:
                    last_status = "429"
                    continue
            if resp.status_code != 200:
                last_status = str(resp.status_code)
                continue
            body, detected = _gtx_body(resp)
            if not body:
                last_status = "empty"
                continue
            return MTResult(
                text=body,
                src=detected or (normalize_lang(src) or "auto"),
                tgt=tgt,
                engine="google-gtx",
                ok=True,
            )
    return MTResult(
        text="",
        src=normalize_lang(src) or "auto",
        tgt=tgt,
        engine=f"google-gtx:{last_status}",
        ok=False,
    )


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


def _cache_key(src: str, tgt: str, text: str, *, engine: str = "") -> str:
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()[:20]
    if engine:
        return f"mt:{engine}:{src}:{tgt}:{digest}"
    return f"mt:{src}:{tgt}:{digest}"


async def _cache_get(ck: str) -> dict | None:
    hit = cache.get(ck)
    if not (isinstance(hit, dict) and hit.get("text")):
        from app.store import mt_cache

        hit = await mt_cache.get(ck)
        if isinstance(hit, dict) and hit.get("text"):
            cache.set(ck, hit, ttl_s=6 * 3600)
    if isinstance(hit, dict) and hit.get("text"):
        return hit
    return None


def _cache_put(ck: str, result: MTResult) -> None:
    payload = result.as_dict() | {"text": result.text}
    cache.set(ck, payload, ttl_s=6 * 3600)
    from app.store import mt_cache

    mt_cache.put(ck, payload)


def _sidecar_pair(src: str, tgt: str) -> tuple[str, str] | None:
    """Flores pair for English ↔ one scheduled language. Other pairs stay on Google."""
    src_n = normalize_lang(src) or src
    tgt_n = normalize_lang(tgt) or tgt
    if src_n == "en" and tgt_n in SCHEDULED_22:
        return _FLORES["en"], _FLORES[tgt_n]
    if tgt_n == "en" and src_n in SCHEDULED_22:
        return _FLORES[src_n], _FLORES["en"]
    return None


def _sentence_pieces(text: str, limit: int = _SENTENCE_CAP) -> list[str]:
    """Split a protected document into sentences the 200M model can take in one call."""
    raw = (text or "").strip()
    if not raw:
        return []
    bits = [p.strip() for p in re.split(r"(?<=[।.!?])\s+|\n+", raw) if p and p.strip()]
    if not bits:
        bits = [raw]
    out: list[str] = []
    for bit in bits:
        if len(bit) <= limit:
            out.append(bit)
            continue
        buf = ""
        for word in bit.split(" "):
            if not word:
                continue
            if len(word) > limit:
                if buf:
                    out.append(buf)
                    buf = ""
                for i in range(0, len(word), limit):
                    out.append(word[i : i + limit])
                continue
            if buf and len(buf) + 1 + len(word) > limit:
                out.append(buf)
                buf = word
                continue
            buf = f"{buf} {word}" if buf else word
        if buf:
            out.append(buf)
    return out


def _shield_locks(text: str) -> str:
    """Swap ⟦n⟧ for a numeral IndicTrans2's processor copies, then restores.

    Spaces keep two adjacent locks from gluing into one numeral. Google still
    receives the bracket tokens.
    """

    def repl(m: re.Match[str]) -> str:
        i = int(m.group(1))
        return f" 9{i:04d}-7{i:04d} "

    return _LOCK_RE.sub(repl, text or "")


def _unshield_locks(text: str) -> str:
    out = re.sub(
        r"(?<!\d)9(\d{4})\s*-\s*7\1(?!\d)",
        lambda m: f"⟦{int(m.group(1))}⟧",
        text or "",
    )
    return re.sub(r" {2,}", " ", out)


def _reject_reason(original: str, body: str, tgt: str, held: list[str], engine: str) -> str | None:
    if "⟦" in body or "⟧" in body:
        return f"{engine}-leaked-lock"
    if held_missing(body, held):
        return f"{engine}-lost-lock"
    if _still_source_script(original, body, tgt):
        return f"{engine}-still-source-script"
    if tgt != "en" and not _plausible(original, body, tgt):
        return f"{engine}-implausible"
    return None


async def _indictrans(text: str, src: str, tgt: str) -> MTResult | None:
    """One document via the sidecar. None lets the caller fall through to Google."""
    pair = _sidecar_pair(src, tgt)
    base = (get_settings().mt_sidecar_url or "").strip().rstrip("/")
    if pair is None or not base:
        return None
    pieces = _sentence_pieces(text)
    if not pieces:
        return None
    src_f, tgt_f = pair
    src_n = normalize_lang(src) or src
    tgt_n = normalize_lang(tgt) or tgt

    async def _run(client: httpx.AsyncClient) -> list[str] | None:
        out: list[str] = []
        for piece in pieces:
            try:
                resp = await client.post(
                    f"{base}/translate",
                    json={"text": _shield_locks(piece), "src": src_f, "tgt": tgt_f},
                )
            except httpx.HTTPError:
                return None
            if resp.status_code != 200:
                return None
            try:
                data = resp.json()
            except Exception:
                return None
            body = data.get("text") if isinstance(data, dict) else None
            if not isinstance(body, str) or not body.strip():
                return None
            out.append(_unshield_locks(body))
        return out

    try:
        timeout = httpx.Timeout(_SIDECAR_BUDGET_S, connect=2.0)
        async with httpx.AsyncClient(timeout=timeout) as client:
            bits = await asyncio.wait_for(_run(client), timeout=_SIDECAR_BUDGET_S)
    except (httpx.HTTPError, asyncio.TimeoutError, OSError):
        return None
    if not bits:
        return None
    return MTResult(
        text=" ".join(bits).strip(),
        src=src_n,
        tgt=tgt_n,
        engine="indictrans2",
        ok=True,
    )


def _still_source_script(original: str, translated: str, tgt: str) -> bool:
    """True when a non-English source was not actually rendered into English."""
    if tgt != "en":
        return False
    src_script = script_of(original)
    if not src_script:
        return False
    out_script = script_of(translated)
    return out_script == src_script


async def translate(text: str, src: str, tgt: str, *, whole: bool = True) -> MTResult:
    """Translate `text` from `src` (or auto) to `tgt`. Prefer one whole-document call."""
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

    if tgt_n == "hinglish":
        hindi = await translate(blob, src_n, "hi", whole=whole)
        if not hindi.ok:
            return MTResult(text=blob, src=src_n, tgt=tgt_n, engine=hindi.engine, ok=False)
        from app.i18n.romanize import deva_to_latin

        return MTResult(
            text=deva_to_latin(hindi.text),
            src=hindi.src,
            tgt=tgt_n,
            engine=f"{hindi.engine}+romanize",
            ok=True,
        )

    # Exact pair first, so Bodo and Kashmiri are not rewritten to Hindi/Urdu
    # while the sidecar is up. A miss falls through to VIA + Google below.
    if (settings.mt_sidecar_url or "").strip() and _sidecar_pair(src_n, tgt_n):
        it_ck = _cache_key(src_n, tgt_n, blob, engine="it2")
        hit = await _cache_get(it_ck)
        if hit:
            return MTResult(
                text=hit["text"],
                src=hit.get("src") or src_n,
                tgt=tgt_n,
                engine=hit.get("engine") or "indictrans2",
                ok=True,
            )
        masked, held = protect(blob)
        local = await _indictrans(masked, src_n, tgt_n)
        if local is not None and local.ok and local.text:
            body = restore(local.text, held)
            if _reject_reason(blob, body, tgt_n, held, "indictrans2") is None:
                result = MTResult(
                    text=body,
                    src=local.src or src_n,
                    tgt=tgt_n,
                    engine="indictrans2",
                    ok=True,
                )
                _cache_put(it_ck, result)
                return result

    if tgt_n in VIA:
        routed = await translate(blob, src_n, VIA[tgt_n], whole=whole)
        if routed.ok:
            routed.engine = f"{routed.engine}:via-{VIA[tgt_n]}"
        routed.tgt = VIA[tgt_n]
        return routed
    if src_n in VIA or src_n == "hinglish":
        src_n = "auto"

    ck = _cache_key(src_n, tgt_n, blob)
    hit = await _cache_get(ck)
    if hit:
        return MTResult(
            text=hit["text"],
            src=hit.get("src") or src_n,
            tgt=tgt_n,
            engine=hit.get("engine") or "cache",
            ok=True,
        )

    masked, held = protect(blob)
    layouts = [[masked]] if whole else [_chunks(masked, 900)]
    if whole:
        layouts.append(_chunks(masked, 900))
    last_err = "none"
    for pieces in layouts:
        factories = (_gtx,) if (tgt_n in _NO_MYMEMORY or src_n in _NO_MYMEMORY) else (_gtx, _mymemory)
        for factory in factories:
            translated: list[str] = []
            detected = src_n
            engine = "none"
            failed = False
            for piece in pieces:
                pack = await factory(piece, src_n if src_n != "auto" else "auto", tgt_n)
                if pack is None or not pack.ok or not pack.text:
                    failed = True
                    last_err = (pack.engine if pack and pack.engine else factory.__name__)
                    break
                translated.append(pack.text)
                detected = pack.src or detected
                engine = pack.engine
            if failed:
                continue
            body = restore("\n".join(translated), held)
            reason = _reject_reason(blob, body, tgt_n, held, engine)
            if reason:
                last_err = reason
                continue
            result = MTResult(text=body, src=detected or src_n, tgt=tgt_n, engine=engine, ok=True)
            _cache_put(ck, result)
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


async def inbound(text: str, hint: str | None = None, picked: str | None = None) -> MTResult:
    """Detect language, then machine-translate the whole utterance to English for the LLM."""
    blob = text or ""
    detected = detect_lang(blob, hint, picked)
    if not blob.strip() or detected == "en":
        return _identity(blob, detected or "en", "en")
    result = await translate(blob, detected, "en", whole=True)
    if result.ok and not _still_source_script(blob, result.text, "en"):
        result.src = detected
        return result
    fallback = await translate(blob, "auto", "en", whole=True)
    if fallback.ok and not _still_source_script(blob, fallback.text, "en"):
        fallback.src = fallback.src if fallback.src not in {"auto", ""} else detected
        return fallback
    failed = result if not result.ok else fallback
    return MTResult(text=blob, src=detected, tgt="en", engine=failed.engine, ok=False)


async def outbound(text: str, tgt: str, src: str = "en") -> MTResult:
    """Validated English draft → reply language as one document (not sentence-spliced)."""
    blob = text or ""
    tgt_n = normalize_lang(tgt) or tgt or "en"
    if tgt_n == "en" or not blob.strip():
        return _identity(blob, "en", tgt_n)
    result = await translate(blob, src or "en", tgt_n, whole=True)
    if result.ok and has_script(result.text, VIA.get(tgt_n, tgt_n)):
        return result
    return MTResult(text=blob, src="en", tgt=tgt_n, engine=result.engine, ok=False)

"""Proxy to optional VEXYL-STT / VEXYL-TTS sidecars. No torch in this process."""

from __future__ import annotations

import asyncio
import base64
import re
import time
from typing import Any

import httpx

from app.config import get_settings

STT_LANGS = (
    "as",
    "bn",
    "gu",
    "hi",
    "kn",
    "ml",
    "mr",
    "or",
    "pa",
    "ta",
    "te",
    "ur",
    "sa",
    "ne",
)
TTS_LANGS = (
    "as",
    "bn",
    "brx",
    "doi",
    "gu",
    "hi",
    "kn",
    "ks",
    "kok",
    "mai",
    "ml",
    "mni",
    "mr",
    "ne",
    "or",
    "pa",
    "sa",
    "sat",
    "sd",
    "ta",
    "te",
    "ur",
    "en",
)

_BCP = {
    "as": "as-IN",
    "bn": "bn-IN",
    "brx": "brx-IN",
    "doi": "doi-IN",
    "gu": "gu-IN",
    "hi": "hi-IN",
    "kn": "kn-IN",
    "ks": "ks-IN",
    "kok": "kok-IN",
    "mai": "mai-IN",
    "ml": "ml-IN",
    "mni": "mni-IN",
    "mr": "mr-IN",
    "ne": "ne-IN",
    "or": "or-IN",
    "pa": "pa-IN",
    "sa": "sa-IN",
    "sat": "sat-IN",
    "sd": "sd-IN",
    "ta": "ta-IN",
    "te": "te-IN",
    "ur": "ur-IN",
    "en": "en-IN",
}

TTS_MAX_CHARS = 800
STT_MAX_BYTES = 8 * 1024 * 1024

_status_cache: dict[str, Any] | None = None
_status_at = 0.0


def reset_status_cache() -> None:
    global _status_cache, _status_at
    _status_cache = None
    _status_at = 0.0


def bcp_for(lang_id: str) -> str:
    key = (lang_id or "hi").split("-")[0].lower()
    return _BCP.get(key, "hi-IN")


def lang_id(code: str) -> str:
    raw = (code or "hi").strip().lower().replace("_", "-")
    return raw.split("-")[0] if raw else "hi"


def plain_for_speech(md: str) -> str:
    return re.sub(
        r"\s+",
        " ",
        (md or "")
        .replace("```", " ")
        .replace("`", "")
        .replace("*", "")
        .replace("_", " ")
        .replace("~", ""),
    ).strip()


def _headers() -> dict[str, str]:
    key = (get_settings().vexyl_api_key or "").strip()
    h = {"Accept": "application/json"}
    if key:
        h["X-API-Key"] = key
    return h


def _base(url: str) -> str:
    return (url or "").rstrip("/")


async def _health(url: str) -> bool:
    if not url:
        return False
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(2.5, connect=1.5)) as c:
            r = await c.get(f"{_base(url)}/health", headers=_headers())
            if r.status_code >= 400:
                return False
            try:
                body = r.json()
            except Exception:
                return True
            st = str(body.get("status") or "ok").lower()
            return st in {"ok", "ready", "healthy"}
    except Exception:
        return False


async def sidecar_status(*, force: bool = False) -> dict[str, Any]:
    global _status_cache, _status_at
    now = time.monotonic()
    if not force and _status_cache is not None and now - _status_at < 30:
        return _status_cache
    s = get_settings()
    stt_url = (s.vexyl_stt_url or "").strip()
    tts_url = (s.vexyl_tts_url or "").strip()
    stt_ok, tts_ok = await asyncio.gather(_health(stt_url), _health(tts_url))
    _status_cache = {
        "stt": bool(stt_ok),
        "tts": bool(tts_ok),
        "stt_langs": list(STT_LANGS) if stt_ok else [],
        "tts_langs": list(TTS_LANGS) if tts_ok else [],
        "fallback": "web-speech",
        "engine": {
            "stt": "vexyl-indic-conformer" if stt_ok else None,
            "tts": "vexyl-indic-parler" if tts_ok else None,
        },
    }
    _status_at = now
    return _status_cache


async def _poll_json(client: httpx.AsyncClient, url: str, job_id: str, *, kind: str, timeout_s: float) -> dict:
    deadline = time.monotonic() + timeout_s
    last: dict = {}
    while time.monotonic() < deadline:
        for path in (
            f"{url}/batch/status/{job_id}",
            f"{url}/batch/result/{job_id}",
        ):
            r = await client.get(path, headers=_headers())
            if r.status_code == 202:
                continue
            if r.status_code >= 400:
                raise RuntimeError(f"{kind} sidecar {r.status_code}")
            try:
                last = r.json()
            except Exception:
                last = {}
            status = str(last.get("status") or "").lower()
            if status in {"failed", "error"}:
                raise RuntimeError(str(last.get("error") or last.get("message") or f"{kind} failed"))
            if kind == "stt" and (last.get("text") or last.get("transcript")):
                return last
            if kind == "tts" and (last.get("audio_b64") or last.get("audio")):
                return last
            if status in {"completed", "done", "ok"}:
                return last
        await asyncio.sleep(0.25)
    raise TimeoutError(f"{kind} timed out")


async def transcribe(data: bytes, filename: str, language: str) -> dict[str, str]:
    s = get_settings()
    url = _base(s.vexyl_stt_url)
    if not url:
        raise RuntimeError("stt_unconfigured")
    lid = lang_id(language)
    if lid not in STT_LANGS:
        raise ValueError("stt_lang")
    if not data:
        raise ValueError("empty_audio")
    if len(data) > STT_MAX_BYTES:
        raise ValueError("audio_too_large")
    name = filename or "clip.wav"
    async with httpx.AsyncClient(timeout=httpx.Timeout(45.0, connect=5.0)) as c:
        r = await c.post(
            f"{url}/batch/transcribe",
            headers=_headers(),
            files={"file": (name, data, "application/octet-stream")},
            data={"language_code": bcp_for(lid)},
        )
        if r.status_code >= 400:
            raise RuntimeError(f"stt sidecar {r.status_code}")
        job = r.json()
        text = job.get("text") or job.get("transcript")
        if text:
            return {"text": str(text).strip(), "lang": lid}
        job_id = job.get("job_id")
        if not job_id:
            raise RuntimeError("stt_no_job")
        done = await _poll_json(c, url, str(job_id), kind="stt", timeout_s=30.0)
        text = done.get("text") or done.get("transcript") or ""
        return {"text": str(text).strip(), "lang": lid}


def _audio_bytes(payload: dict) -> tuple[bytes, str]:
    b64 = payload.get("audio_b64") or payload.get("audio")
    if isinstance(b64, str) and b64:
        raw = base64.b64decode(b64)
        return raw, "audio/wav"
    raise RuntimeError("tts_no_audio")


async def synthesize(text: str, language: str, style: str | None = None) -> tuple[bytes, str]:
    s = get_settings()
    url = _base(s.vexyl_tts_url)
    if not url:
        raise RuntimeError("tts_unconfigured")
    lid = lang_id(language)
    if lid not in TTS_LANGS:
        raise ValueError("tts_lang")
    spoken = plain_for_speech(text)[:TTS_MAX_CHARS]
    if not spoken:
        raise ValueError("empty_text")
    body = {"text": spoken, "lang": bcp_for(lid), "style": style or "default"}
    async with httpx.AsyncClient(timeout=httpx.Timeout(200.0, connect=5.0)) as c:
        r = await c.post(f"{url}/batch/synthesize", headers={**_headers(), "Content-Type": "application/json"}, json=body)
        if r.status_code >= 400:
            raise RuntimeError(f"tts sidecar {r.status_code}")
        job = r.json()
        if job.get("audio_b64") or job.get("audio"):
            return _audio_bytes(job)
        job_id = job.get("job_id")
        if not job_id:
            raise RuntimeError("tts_no_job")
        done = await _poll_json(c, url, str(job_id), kind="tts", timeout_s=180.0)
        return _audio_bytes(done)

"""Small payloads for the ESP32 weather box.

The full dashboard does not fit the 30-pin board. The OLED reads `oled_card`.
Speech is one WAV in and one 16 kHz WAV out. Speech-to-text is English only.
"""

from __future__ import annotations

import io
import re
import struct
import wave
from typing import Any

from app.services.speech import plain_for_speech

SPOKEN_MAX = 180
# 16 kHz mono 16-bit for about 14 seconds. The board scratch partition is 512 KB.
PCM_MAX_BYTES = 14 * 16000 * 2

_whisper = None


def oled_card(snap: Any) -> dict[str, Any]:
    """Fields the 128x64 face can draw. Numbers come only from the snapshot."""
    cur = snap.descriptive.current
    loc = snap.location
    place = (getattr(loc, "place_name", None) or getattr(loc, "label", None) or "")[:40]
    aqi = cur.aqi if cur.aqi is not None else cur.om_us_aqi
    hazard = ""
    action = ""
    warnings = list(getattr(snap.prescriptive, "warnings", None) or [])
    actions = list(getattr(snap.prescriptive, "actions", None) or [])
    if warnings:
        hazard = str(getattr(warnings[0], "hazard", "") or "weather")[:16]
        action = str(getattr(warnings[0], "title", "") or "")[:80]
    elif actions:
        action = str(getattr(actions[0], "action", "") or "")[:80]
    return {
        "place": place,
        "temp_c": cur.temp_c,
        "sky_kind": (cur.sky_kind or "")[:16],
        "precip_1h_mm": cur.precip_1h_mm,
        "aqi": aqi,
        "is_day": bool(cur.is_day) if cur.is_day is not None else True,
        "hazard": hazard,
        "action": action,
    }


def spoken_from_card(card: dict[str, Any]) -> str:
    """One true sentence from the OLED card. Uses only numbers already on the card."""
    place = str(card.get("place") or "").strip() or "this place"
    temp = card.get("temp_c")
    sky = str(card.get("sky_kind") or "").replace("_", " ").strip()
    aqi = card.get("aqi")
    if temp is None and aqi is None:
        return f"I am still checking the weather for {place}. Ask again in a moment."
    parts: list[str] = []
    if temp is not None:
        if sky:
            parts.append(f"In {place} it is {temp} degrees under {sky} skies.")
        else:
            parts.append(f"In {place} it is {temp} degrees.")
    if aqi is not None:
        parts.append(f"The air quality index is {aqi}.")
    return " ".join(parts)


def clip_spoken(text: str) -> str:
    spoken = plain_for_speech(text or "")
    if len(spoken) <= SPOKEN_MAX:
        return spoken
    cut = spoken[:SPOKEN_MAX]
    for mark in (". ", "। ", "? ", "! "):
        at = cut.rfind(mark)
        if at > 40:
            return cut[: at + 1].strip()
    at = cut.rfind(" ")
    return (cut[:at] if at > 40 else cut).strip()


def wav_mono16(pcm: bytes, rate: int) -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(rate)
        wf.writeframes(pcm)
    return buf.getvalue()


def parse_wav_mono16(blob: bytes) -> tuple[bytes, int]:
    """Return mono 16-bit PCM and sample rate. Stereo keeps the left channel."""
    with wave.open(io.BytesIO(blob), "rb") as wf:
        channels = wf.getnchannels()
        width = wf.getsampwidth()
        rate = wf.getframerate()
        frames = wf.readframes(wf.getnframes())
    if width != 2:
        raise ValueError("wav_width")
    if channels == 1:
        return frames, rate
    if channels != 2:
        raise ValueError("wav_channels")
    out = bytearray()
    for i in range(0, len(frames) - 3, 4):
        out += frames[i : i + 2]
    return bytes(out), rate


def resample_pcm16(pcm: bytes, src_rate: int, dst_rate: int = 16000) -> bytes:
    """Linear resample, mono 16-bit. Uses audioop on Python 3.12."""
    if src_rate == dst_rate or not pcm:
        return pcm
    if len(pcm) % 2:
        pcm = pcm[:-1]
    try:
        import audioop

        converted, _state = audioop.ratecv(pcm, 2, 1, src_rate, dst_rate, None)
        return converted
    except Exception:
        pass
    count = len(pcm) // 2
    if count < 2:
        return pcm
    samples = struct.unpack("<" + "h" * count, pcm)
    out_n = max(1, int(round(count * dst_rate / src_rate)))
    out = []
    last = count - 1
    for i in range(out_n):
        pos = i * src_rate / dst_rate
        j = int(pos)
        if j >= last:
            out.append(samples[last])
            continue
        frac = pos - j
        mixed = samples[j] * (1.0 - frac) + samples[j + 1] * frac
        mixed = max(-32768, min(32767, int(round(mixed))))
        out.append(mixed)
    return struct.pack("<" + "h" * len(out), *out)


def fit_pcm(pcm: bytes) -> bytes:
    if len(pcm) <= PCM_MAX_BYTES:
        return pcm
    return pcm[: PCM_MAX_BYTES - (PCM_MAX_BYTES % 2)]


def _english_model():
    global _whisper
    if _whisper is not None:
        return _whisper
    try:
        from faster_whisper import WhisperModel
    except Exception as exc:
        raise RuntimeError("stt_unconfigured") from exc
    from app.config import get_settings

    settings = get_settings()
    _whisper = WhisperModel(
        settings.whisper_model or "small",
        device=settings.whisper_device or "cpu",
        compute_type=settings.whisper_compute or "int8",
    )
    return _whisper


# Folder names on the local FastSpeech2 server (ai-tts POST /api/speak).
_FS2 = {
    "as": "assamese",
    "bn": "bengali",
    "brx": "bodo",
    "en": "english",
    "gu": "gujarati",
    "hi": "hindi",
    "kn": "kannada",
    "ml": "malayalam",
    "mni": "manipuri",
    "mr": "marathi",
    "or": "odia",
    "pa": "punjabi",
    "ta": "tamil",
    "te": "telugu",
    "ur": "urdu",
}


def fs2_language(code: str) -> str | None:
    """FastSpeech2 name for a chat language, or None when that server has no voice."""
    return _FS2.get(code)


# The unified parser indexes a symbol table by language id. A token whose first
# character is outside those scripts (the degree sign in "32 °C") raises
# IndexError and the speak request returns 500.
_FS2_DROP = re.compile(
    r"[^\u0900-\u097F\u0980-\u09FF\u0A00-\u0A7F\u0A80-\u0AFF"
    r"\u0B00-\u0B7F\u0B80-\u0BFF\u0C00-\u0C7F\u0C80-\u0CFF\u0D00-\u0D7F"
    r"\u0600-\u06FF\u1C50-\u1C7F\uABC0-\uABFF\uAAE0-\uAAFF"
    r"A-Za-z0-9\s.,;:!?%'\"()\-]"
)


def fs2_text(text: str) -> str:
    """Keep letters the local speaker can parse. Drop the degree sign and similar symbols."""
    cleaned = _FS2_DROP.sub(" ", text or "")
    return re.sub(r"\s+", " ", cleaned).strip()


async def speak_local(text: str, language: str, timeout_s: float = 180.0) -> tuple[bytes, str]:
    """WAV from the local FastSpeech2 server in `language` (a chat code, not a folder name)."""
    import httpx

    from app.config import get_settings

    name = fs2_language(language)
    if not name:
        raise RuntimeError("tts_lang")
    spoken = fs2_text(text)
    if not spoken:
        raise RuntimeError("tts_failed")
    settings = get_settings()
    url = (settings.local_tts_url or "http://127.0.0.1:7860").rstrip("/")
    async with httpx.AsyncClient(timeout=httpx.Timeout(timeout_s, connect=2.0)) as client:
        response = await client.post(
            f"{url}/api/speak",
            json={"text": spoken, "language": name, "gender": "female"},
        )
    data = response.content
    if response.status_code >= 400 or not data.startswith(b"RIFF"):
        raise RuntimeError("tts_failed")
    return data, "audio/wav"


async def speak_english(text: str, timeout_s: float = 60.0) -> tuple[bytes, str]:
    """English WAV from the local FastSpeech2 server."""
    return await speak_local(text, "en", timeout_s)


def local_tts_codes() -> list[str]:
    """Chat codes whose female FastSpeech2 voice is loaded. Empty when the server is down."""
    import httpx

    from app.config import get_settings

    by_name = {name: code for code, name in _FS2.items()}
    settings = get_settings()
    url = (settings.local_tts_url or "http://127.0.0.1:7860").rstrip("/")
    try:
        response = httpx.get(f"{url}/api/languages", timeout=1.5)
        rows = response.json() if response.status_code == 200 else []
    except Exception:
        return []
    codes: list[str] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        code = by_name.get(str(row.get("language") or ""))
        genders = row.get("genders") or []
        if code and "female" in genders:
            codes.append(code)
    return codes


def voice_ready() -> dict[str, Any]:
    import importlib.util

    stt = importlib.util.find_spec("faster_whisper") is not None
    codes = local_tts_codes()
    tts = "en" in codes
    notes = []
    if not stt:
        notes.append("English recognition is not installed on this computer.")
    if not tts:
        notes.append("The speaking service is not running.")
    return {"stt": stt, "tts": tts, "detail": " ".join(notes), "langs": codes}


def _open_audio_compat() -> None:
    """faster-whisper 1.2.1 still passes metadata_errors, which PyAV 19 removed."""
    import av

    if getattr(av.open, "_prithvi_audio", False):
        return
    major = int(str(getattr(av, "__version__", "0")).split(".")[0] or "0")
    if major < 19:
        return
    original = av.open

    def open_compat(*args, **kwargs):
        kwargs.pop("metadata_errors", None)
        return original(*args, **kwargs)

    open_compat._prithvi_audio = True  # type: ignore[attr-defined]
    av.open = open_compat


def _whisper_lang(code: str | None) -> str:
    raw = (code or "en").split("-")[0].lower()
    return {"od": "or", "gom": "kok"}.get(raw, raw)


def _transcribe_file(data: bytes, language: str | None) -> tuple[str, str]:
    import os
    import tempfile

    _open_audio_compat()
    model = _english_model()
    fd, path = tempfile.mkstemp(suffix=".wav")
    try:
        os.write(fd, data)
        os.close(fd)
        fd = -1
        kwargs: dict = {
            "vad_filter": True,
            "beam_size": 1,
            "best_of": 1,
            "condition_on_previous_text": False,
        }
        if language:
            kwargs["language"] = language
        segments, info = model.transcribe(path, **kwargs)
        text = " ".join((seg.text or "").strip() for seg in segments).strip()
        detected = _whisper_lang(getattr(info, "language", None) or language)
        return text, detected
    finally:
        if fd >= 0:
            os.close(fd)
        try:
            os.remove(path)
        except OSError:
            pass


def transcribe_english(data: bytes) -> str:
    """English only. The weather box and English chat both use this."""
    text, _lang = _transcribe_file(data, "en")
    return text


def transcribe_detect(data: bytes) -> dict[str, str]:
    """One Whisper pass that also reports the detected language code.

    IndicConformer still needs that code. This does not call it.
    """
    text, lang = _transcribe_file(data, None)
    return {"text": text, "lang": lang}

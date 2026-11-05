import asyncio

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel, Field

from app.services import speech as voice

router = APIRouter()


class TtsIn(BaseModel):
    text: str = Field(..., min_length=1, max_length=5000)
    language: str = "hi"
    voice: str | None = None


@router.get("/speech/status", summary="Indic STT/TTS sidecar availability")
async def speech_status():
    return await voice.sidecar_status()


def _stt_http(exc: Exception) -> HTTPException:
    if isinstance(exc, ValueError):
        code = str(exc)
        if code == "stt_lang":
            return HTTPException(
                status_code=501,
                detail={"error": "stt_lang", "fallback": "web-speech", "stt_langs": list(voice.STT_LANGS)},
            )
        return HTTPException(status_code=400, detail=code)
    if isinstance(exc, TimeoutError):
        return HTTPException(status_code=504, detail="stt_timeout")
    msg = str(exc)
    if msg == "stt_unconfigured":
        return HTTPException(status_code=503, detail={"error": msg, "fallback": "web-speech"})
    return HTTPException(status_code=502, detail=msg)


async def _local_stt(data: bytes, filename: str, lid: str) -> dict[str, str]:
    """English, Hinglish, and Auto use faster-whisper. Auto may retry one Indic language."""
    if not data:
        raise HTTPException(status_code=400, detail="empty_audio")
    if len(data) > voice.STT_MAX_BYTES:
        raise HTTPException(status_code=400, detail="audio_too_large")
    from app.services import device_hw

    try:
        if lid == "auto":
            found = await asyncio.to_thread(device_hw.transcribe_detect, data)
        else:
            text = await asyncio.to_thread(device_hw.transcribe_english, data)
            found = {"text": text, "lang": "en"}
    except RuntimeError as e:
        raise _stt_http(e) from e
    code = voice.lang_id(str(found.get("lang") or "en"))
    text = str(found.get("text") or "").strip()
    if lid != "auto" or code not in voice.STT_LANGS:
        return {"text": text, "lang": "en" if lid != "auto" else code}
    try:
        indic = await voice.transcribe(data, filename, code)
    except Exception:
        return {"text": text, "lang": code}
    heard = str(indic.get("text") or "").strip()
    if heard:
        return {"text": heard, "lang": code}
    return {"text": text, "lang": code}


@router.post("/speech/stt", summary="Transcribe an utterance")
async def speech_stt(
    file: UploadFile = File(...),
    language: str = Form("hi"),
):
    data = await file.read()
    lid = voice.lang_id(language)
    if lid in {"en", "hinglish", "auto"}:
        return await _local_stt(data, file.filename or "clip.wav", lid)
    try:
        return await voice.transcribe(data, file.filename or "clip.wav", language)
    except (ValueError, RuntimeError, TimeoutError) as e:
        raise _stt_http(e) from e


@router.post("/speech/tts", summary="Synthesize speech")
async def speech_tts(body: TtsIn):
    lid = voice.lang_id(body.language)
    spoken = voice.plain_for_speech(body.text)[: voice.TTS_MAX_CHARS]
    if not spoken:
        raise HTTPException(status_code=400, detail="empty_text")
    if lid in {"en", "hinglish"}:
        from app.services import device_hw

        try:
            audio, mime = await device_hw.speak_english(spoken)
        except RuntimeError as e:
            raise HTTPException(
                status_code=503,
                detail={"error": str(e) or "tts_failed", "fallback": "web-speech"},
            ) from e
        return Response(content=audio, media_type=mime)
    from app.services import device_hw

    if not device_hw.fs2_language(lid):
        raise HTTPException(
            status_code=501,
            detail={
                "error": "tts_lang",
                "fallback": "web-speech",
                "tts_langs": [c for c in voice.TTS_LANGS if device_hw.fs2_language(c)],
            },
        )
    try:
        audio, mime = await device_hw.speak_local(spoken, lid)
    except RuntimeError as e:
        raise HTTPException(
            status_code=503,
            detail={"error": str(e) or "tts_failed", "fallback": "web-speech"},
        ) from e
    return Response(content=audio, media_type=mime)

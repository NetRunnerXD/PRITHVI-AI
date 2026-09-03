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


@router.post("/speech/stt", summary="Transcribe an utterance via VEXYL-STT")
async def speech_stt(
    file: UploadFile = File(...),
    language: str = Form("hi"),
):
    data = await file.read()
    try:
        return await voice.transcribe(data, file.filename or "clip.wav", language)
    except ValueError as e:
        code = str(e)
        if code == "stt_lang":
            raise HTTPException(
                status_code=501,
                detail={"error": "stt_lang", "fallback": "web-speech", "stt_langs": list(voice.STT_LANGS)},
            ) from e
        raise HTTPException(status_code=400, detail=code) from e
    except RuntimeError as e:
        msg = str(e)
        if msg == "stt_unconfigured":
            raise HTTPException(status_code=503, detail={"error": msg, "fallback": "web-speech"}) from e
        raise HTTPException(status_code=502, detail=msg) from e
    except TimeoutError as e:
        raise HTTPException(status_code=504, detail="stt_timeout") from e


@router.post("/speech/tts", summary="Synthesize speech via VEXYL-TTS")
async def speech_tts(body: TtsIn):
    try:
        audio, mime = await voice.synthesize(body.text, body.language, body.voice)
    except ValueError as e:
        code = str(e)
        if code == "tts_lang":
            raise HTTPException(
                status_code=501,
                detail={"error": "tts_lang", "fallback": "web-speech", "tts_langs": list(voice.TTS_LANGS)},
            ) from e
        raise HTTPException(status_code=400, detail=code) from e
    except RuntimeError as e:
        msg = str(e)
        if msg == "tts_unconfigured":
            raise HTTPException(status_code=503, detail={"error": msg, "fallback": "web-speech"}) from e
        raise HTTPException(status_code=502, detail=msg) from e
    except TimeoutError as e:
        raise HTTPException(status_code=504, detail="tts_timeout") from e
    return Response(content=audio, media_type=mime)

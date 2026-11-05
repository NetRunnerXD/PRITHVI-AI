"""ESP32 weather-box routes.

`GET /device/face` is the idle OLED card.
`POST /device/turn` takes a 16 kHz WAV and returns a 16 kHz WAV.
Speech-to-text is English only. The reply is spoken in English.
"""

from __future__ import annotations

import asyncio
import logging
import time
from urllib.parse import quote

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse, Response
from starlette.requests import ClientDisconnect

from app.agents.orchestrator import run_agent
from app.api.deps import loc_from_query
from app.schemas.chat import ChatRequest
from app.schemas.location import Location
from app.services.device_hw import (
    clip_spoken,
    fit_pcm,
    oled_card,
    parse_wav_mono16,
    resample_pcm16,
    speak_english,
    spoken_from_card,
    transcribe_english,
    voice_ready,
    wav_mono16,
)
from app.services import device_link
from app.services.snapshot import build_core, peek_snapshot

router = APIRouter()
log = logging.getLogger("prithvi.device")

# The OLED stays on ASKING until the first WAV byte. A tool-heavy question must not sit there
# for the full model budget. Past this, the box speaks the card it already has.
_ANSWER_S = 18.0
_TTS_S = 15.0


def _header(value: object) -> str:
    text = "" if value is None else str(value)
    try:
        text.encode("latin-1")
        return text
    except UnicodeEncodeError:
        return quote(text, safe="")


def _reply_text(message: object) -> str:
    if message is None:
        return ""
    if isinstance(message, dict):
        return str(message.get("content") or "")
    return str(getattr(message, "content", "") or "")


def _wav_response(wav: bytes, card: dict) -> Response:
    headers = {
        "X-Prithvi-Lang": "en",
        "X-Prithvi-Fallback": "",
        "X-Prithvi-Place": _header(card.get("place") or ""),
        "X-Prithvi-Temp": _header("" if card.get("temp_c") is None else card.get("temp_c")),
        "X-Prithvi-Sky": _header(card.get("sky_kind") or ""),
        "X-Prithvi-Rain": _header("" if card.get("precip_1h_mm") is None else card.get("precip_1h_mm")),
        "X-Prithvi-Aqi": _header("" if card.get("aqi") is None else card.get("aqi")),
        "X-Prithvi-Day": "1" if card.get("is_day") else "0",
        "X-Prithvi-Hazard": _header(card.get("hazard") or ""),
        "X-Prithvi-Action": _header(card.get("action") or ""),
    }
    return Response(content=wav, media_type="audio/wav", headers=headers)


def _place_card(loc: Location) -> dict:
    label = getattr(loc, "place_name", None) or getattr(loc, "label", None) or ""
    return {
        "place": label,
        "temp_c": None,
        "sky_kind": "",
        "precip_1h_mm": None,
        "aqi": None,
        "is_day": True,
        "hazard": "",
        "action": "",
    }


def _cached_card(loc: Location) -> dict | None:
    snap = peek_snapshot(loc)
    if snap is None or getattr(snap, "enriching", False):
        return None
    return oled_card(snap)


async def _card_for(loc: Location) -> dict:
    try:
        snap, _full = await build_core(loc, "en")
        return oled_card(snap)
    except Exception:
        label = getattr(loc, "place_name", None) or getattr(loc, "label", None) or ""
        return {
            "place": label,
            "temp_c": None,
            "sky_kind": "",
            "precip_1h_mm": None,
            "aqi": None,
            "is_day": True,
            "hazard": "",
            "action": "",
        }


@router.get("/device/face", summary="OLED weather card for the ESP32")
async def device_face(loc: Location = Depends(loc_from_query)):
    snap, _full = await build_core(loc, "en")
    return oled_card(snap)


async def _agent_spoken(text: str, loc: Location) -> str:
    payload = ChatRequest(
        message=text,
        output_locale="en",
        place=None,
        stream=False,
        location=loc,
        voice_box=True,
    )
    final = None
    async for event in run_agent(payload):
        if event.get("type") == "final":
            final = event.get("message")
    return clip_spoken(_reply_text(final))


async def _load_card(loc: Location) -> dict:
    cached = _cached_card(loc)
    if cached is not None:
        return cached
    try:
        return await asyncio.wait_for(_card_for(loc), 8)
    except Exception:
        log.exception("device card")
        return _cached_card(loc) or _place_card(loc)


def _tts_failed(card: dict) -> JSONResponse:
    return JSONResponse(
        status_code=200,
        content={"ok": True, "audio": False, "error": "tts_failed", "lang": "en", "oled": card},
    )


async def _to_wav(spoken: str, timeout_s: float) -> bytes:
    audio, _mime = await speak_english(spoken, timeout_s=timeout_s)
    pcm, rate = parse_wav_mono16(audio)
    return wav_mono16(fit_pcm(resample_pcm16(pcm, rate, 16000)), 16000)


@router.post("/device/turn", summary="English WAV in, 16 kHz English WAV out")
async def device_turn(request: Request, loc: Location = Depends(loc_from_query)):
    started = time.perf_counter()
    try:
        data = await request.body()
    except ClientDisconnect:
        log.info("device turn upload closed")
        return JSONResponse(status_code=400, content={"ok": False, "error": "empty_audio"})
    if len(data) < 44:
        return JSONResponse(status_code=400, content={"ok": False, "error": "empty_audio"})
    if len(data) > 256 * 1024:
        return JSONResponse(status_code=400, content={"ok": False, "error": "audio_too_large"})

    try:
        text = await asyncio.to_thread(transcribe_english, data)
    except RuntimeError as exc:
        code = str(exc)
        status = 503 if code == "stt_unconfigured" else 502
        return JSONResponse(status_code=status, content={"ok": False, "error": code or "stt_failed"})
    except Exception:
        log.exception("device turn stt failed")
        return JSONResponse(status_code=502, content={"ok": False, "error": "stt_failed"})

    if not text:
        return JSONResponse(status_code=400, content={"ok": False, "error": "empty_transcript"})

    heard = time.perf_counter()
    log.info("device heard %.1fs %s", heard - started, text[:80])
    card_task = asyncio.create_task(_load_card(loc))

    def _drop_card(task: asyncio.Task) -> None:
        if task.cancelled():
            return
        err = task.exception()
        if err:
            log.warning("device card dropped: %s", type(err).__name__)

    card_task.add_done_callback(_drop_card)
    spoken = ""
    try:
        spoken = await asyncio.wait_for(_agent_spoken(text, loc), _ANSWER_S)
    except TimeoutError:
        log.warning("device answer budget")
    except Exception:
        log.exception("device turn chat failed")
        spoken = ""

    card = _cached_card(loc) or _place_card(loc)
    if card_task.done():
        try:
            card = card_task.result()
        except Exception:
            log.exception("device card failed")
    else:
        try:
            card = await asyncio.wait_for(asyncio.shield(card_task), 1.5)
        except TimeoutError:
            log.warning("device card still running")
        except Exception:
            log.exception("device card failed")
    if not spoken:
        spoken = clip_spoken(spoken_from_card(card))

    try:
        wav = await _to_wav(spoken, _TTS_S)
    except Exception:
        short = clip_spoken(spoken_from_card(card))
        if not short or short == spoken:
            log.exception("device turn tts failed")
            return _tts_failed(card)
        try:
            wav = await _to_wav(short, 8.0)
            spoken = short
        except Exception:
            log.exception("device turn tts failed")
            return _tts_failed(card)
    log.info("device spoke %.1fs chars %d", time.perf_counter() - started, len(spoken))
    return _wav_response(wav, card)


@router.get("/device/voice", summary="Whether this computer can hear and speak English")
async def device_voice():
    body = await asyncio.to_thread(voice_ready)
    return {"ok": True, **body}


@router.get("/device/nearby", summary="Boxes heard on the LAN or on PRITHVI-SETUP")
async def device_nearby():
    await device_link.probe_setup()
    await device_link.probe_mdns()
    return {"ok": True, "devices": device_link.seen_devices(), "linked": device_link.linked_code()}


@router.post("/device/link", summary="Link the box whose screen shows this code")
async def device_link_post(request: Request):
    body = await request.json()
    code = str((body or {}).get("code") or "")
    try:
        return await device_link.link_code(code)
    except ValueError:
        return JSONResponse(status_code=400, content={"ok": False, "error": "code"})
    except LookupError:
        return JSONResponse(status_code=404, content={"ok": False, "error": "not_found"})


@router.get("/device/box", summary="Status of the linked box")
async def device_box_get():
    try:
        status = await device_link.box_status()
    except LookupError:
        return JSONResponse(status_code=404, content={"ok": False, "error": "link"})
    except ConnectionError:
        return JSONResponse(status_code=502, content={"ok": False, "error": "offline"})
    return {"ok": True, "code": device_link.linked_code(), "status": status}


@router.get("/device/box/bt", summary="Bluetooth speakers last seen by the linked box")
async def device_box_bt_get():
    try:
        return await device_link.box_bt(None)
    except LookupError:
        return JSONResponse(status_code=404, content={"ok": False, "error": "link"})
    except ConnectionError:
        return JSONResponse(status_code=502, content={"ok": False, "error": "offline"})
    except RuntimeError as exc:
        return JSONResponse(status_code=502, content={"ok": False, "error": str(exc) or "bt"})


@router.post("/device/box/bt", summary="Scan, connect, or forget a Bluetooth speaker")
async def device_box_bt_post(request: Request):
    body = await request.json()
    if not isinstance(body, dict):
        return JSONResponse(status_code=400, content={"ok": False, "error": "json"})
    try:
        return await device_link.box_bt(body)
    except LookupError:
        return JSONResponse(status_code=404, content={"ok": False, "error": "link"})
    except ConnectionError:
        return JSONResponse(status_code=502, content={"ok": False, "error": "offline"})
    except RuntimeError as exc:
        return JSONResponse(status_code=502, content={"ok": False, "error": str(exc) or "bt"})


@router.get("/device/box/wifi", summary="Home networks seen by the linked box")
async def device_box_wifi():
    try:
        return await device_link.box_wifi()
    except LookupError:
        return JSONResponse(status_code=404, content={"ok": False, "error": "link"})
    except Exception:
        return JSONResponse(status_code=502, content={"ok": False, "error": "scan"})


@router.post("/device/box", summary="Push Wi-Fi and settings to the linked box")
async def device_box_post(request: Request):
    body = await request.json()
    if not isinstance(body, dict):
        return JSONResponse(status_code=400, content={"ok": False, "error": "json"})
    try:
        return await device_link.push_box(body)
    except LookupError:
        return JSONResponse(status_code=404, content={"ok": False, "error": "link"})
    except ConnectionError:
        return JSONResponse(status_code=502, content={"ok": False, "error": "offline"})
    except RuntimeError as exc:
        return JSONResponse(status_code=502, content={"ok": False, "error": str(exc) or "box"})

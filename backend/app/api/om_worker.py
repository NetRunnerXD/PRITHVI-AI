"""WebSocket for Open-Meteo fetch relays. Same token family as the LLM worker."""

from __future__ import annotations

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.config import get_settings
from app.providers.om_hub import hub

router = APIRouter()


def _want_token() -> str:
    s = get_settings()
    return (s.om_worker_token or s.llm_worker_token or "").strip()


def _token(ws: WebSocket) -> str:
    q = (ws.query_params.get("token") or "").strip()
    if q:
        return q
    auth = (ws.headers.get("authorization") or "").strip()
    if auth.lower().startswith("bearer "):
        return auth[7:].strip()
    return (ws.headers.get("x-llm-worker-token") or ws.headers.get("x-om-worker-token") or "").strip()


@router.get("/om/home", summary="Open-Meteo relay worker status")
async def om_home_status():
    return {
        "ok": True,
        "configured": bool(_want_token()),
        "online": hub.online(),
        "home": hub.status(),
        "ws": "/api/om/worker",
    }


@router.websocket("/om/worker")
async def om_worker(ws: WebSocket):
    want = _want_token()
    got = _token(ws)
    await ws.accept()
    if not want:
        await ws.send_json({"type": "error", "error": "Set LLM_WORKER_TOKEN or OM_WORKER_TOKEN on the API."})
        await ws.close(code=1008)
        return
    if got != want:
        await ws.send_json({"type": "error", "error": "worker token mismatch"})
        await ws.close(code=1008)
        return
    await hub.attach(ws)
    try:
        await ws.send_json({"type": "hello", "ok": True, "role": "om-relay"})
        while True:
            data = await ws.receive_json()
            kind = (data or {}).get("type")
            if kind in {"hello", "pong", "ping"}:
                hub.beat()
                if kind == "ping":
                    await ws.send_json({"type": "pong"})
                continue
            jid = str((data or {}).get("id") or "")
            if kind == "result":
                hub.beat()
                body = data.get("json")
                hub.complete(jid, {"json": body} if isinstance(body, (dict, list)) else {})
            elif kind == "error":
                hub.beat()
                hub.complete(jid, error=str(data.get("error") or "om worker error"))
    except WebSocketDisconnect:
        pass
    except Exception:
        pass
    finally:
        await hub.detach(ws)

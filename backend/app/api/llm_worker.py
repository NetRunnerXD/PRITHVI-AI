"""WebSocket for a home Ollama worker. Auth is a shared server token."""

from __future__ import annotations

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.config import get_settings
from app.llm.worker_hub import hub

router = APIRouter()


def _token(ws: WebSocket) -> str:
    q = (ws.query_params.get("token") or "").strip()
    if q:
        return q
    auth = (ws.headers.get("authorization") or "").strip()
    if auth.lower().startswith("bearer "):
        return auth[7:].strip()
    return (ws.headers.get("x-llm-worker-token") or "").strip()


@router.get("/llm/home", summary="Home Ollama worker status")
async def llm_home_status():
    s = get_settings()
    return {
        "ok": True,
        "configured": bool((s.llm_worker_token or "").strip()),
        "online": hub.online(),
        "home": hub.status(),
        "ws": "/api/llm/worker",
    }


@router.websocket("/llm/worker")
async def llm_worker(ws: WebSocket):
    settings = get_settings()
    want = (settings.llm_worker_token or "").strip()
    got = _token(ws)
    await ws.accept()
    if not want:
        await ws.send_json({"type": "error", "error": "LLM_WORKER_TOKEN is not set on the API. Add it in Render env and restart."})
        await ws.close(code=1008)
        return
    if got != want:
        await ws.send_json({"type": "error", "error": "worker token mismatch"})
        await ws.close(code=1008)
        return
    await hub.attach(ws)
    try:
        await ws.send_json({"type": "hello", "ok": True})
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
                hub.complete(
                    jid,
                    {
                        "content": (data.get("content") or "").strip(),
                        "tool_calls": data.get("tool_calls") or [],
                        "tools_stripped": bool(data.get("tools_stripped")),
                    },
                )
            elif kind == "error":
                hub.beat()
                hub.complete(jid, error=str(data.get("error") or "worker error"))
    except WebSocketDisconnect:
        pass
    except Exception:
        pass
    finally:
        await hub.detach(ws)

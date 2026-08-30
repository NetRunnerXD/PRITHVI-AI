import json

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse, StreamingResponse

from app.agents.orchestrator import run_agent
from app.schemas.chat import ChatRequest
from app.services.location_svc import resolve_location

router = APIRouter()


def _unprocessable(msg: str, raw: str | None = None) -> JSONResponse:
    item: dict = {
        "type": "model_attributes_type",
        "loc": ["body"],
        "msg": msg,
    }
    if raw is not None:
        item["input"] = raw[:500]
    return JSONResponse(status_code=422, content={"detail": [item]})


async def parse_chat_payload(request: Request) -> ChatRequest | JSONResponse:
    raw = (await request.body() or b"").decode("utf-8", "replace").strip()
    if not raw:
        data: object = {}
    else:
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            return _unprocessable(
                'Body must be JSON. In Thunder Client set Body type to JSON (not Text). Example: {"message":"...","stream":false}',
                raw,
            )
        if isinstance(data, str):
            try:
                data = json.loads(data)
            except json.JSONDecodeError:
                return _unprocessable(
                    "Body is a JSON string, not an object. Thunder Client: Body → JSON, paste the object (no wrapping quotes).",
                    data,
                )
    if not isinstance(data, dict):
        return _unprocessable(
            "Input should be a JSON object. Thunder Client: Body type = JSON, not Text.",
            raw,
        )
    return ChatRequest.model_validate(data)


def _want_json(payload: ChatRequest, request: Request) -> bool:
    if payload.stream is False:
        return True
    accept = (request.headers.get("accept") or "").lower()
    if "text/event-stream" in accept:
        return False
    return "application/json" in accept and "text/event-stream" not in accept


@router.post("/chat")
async def chat(request: Request, payload: ChatRequest | JSONResponse = Depends(parse_chat_payload)):
    if isinstance(payload, JSONResponse):
        return payload
    if not (payload.message or "").strip():
        return JSONResponse(
            status_code=422,
            content={
                "detail": [
                    {
                        "type": "missing",
                        "loc": ["body", "message"],
                        "msg": 'Field required. Send JSON {"message": "Will it rain in Haldia?", "stream": false}',
                    }
                ]
            },
        )
    if payload.location is None:
        payload.location = resolve_location(q=payload.place) if payload.place else resolve_location()

    if _want_json(payload, request):
        events: list[dict] = []
        final = None
        async for event in run_agent(payload):
            events.append(event)
            if event.get("type") == "final":
                final = event.get("message")
        return JSONResponse({"ok": True, "stream": False, "events": events, "message": final})

    async def gen():
        async for event in run_agent(payload):
            yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        gen(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )

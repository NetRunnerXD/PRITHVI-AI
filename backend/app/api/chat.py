import json

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from app.agents.orchestrator import run_agent
from app.schemas.chat import ChatRequest
from app.services.location_svc import resolve_location

router = APIRouter()


@router.post("/chat")
async def chat(payload: ChatRequest):
    if payload.location is None:
        payload.location = resolve_location()

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

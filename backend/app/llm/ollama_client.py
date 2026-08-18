from __future__ import annotations

from typing import Any

from openai import AsyncOpenAI

from app.config import get_settings

_client: AsyncOpenAI | None = None


def client() -> AsyncOpenAI:
    global _client
    if _client is None:
        s = get_settings()
        _client = AsyncOpenAI(base_url=s.ollama_base_url, api_key=s.ollama_api_key, timeout=120.0)
    return _client


def _parse_message(msg: Any) -> dict[str, Any]:
    tool_calls = []
    raw = getattr(msg, "tool_calls", None) or []
    for c in raw:
        fn = getattr(c, "function", None)
        tool_calls.append(
            {
                "id": getattr(c, "id", None) or "call",
                "name": getattr(fn, "name", None) if fn else None,
                "arguments": getattr(fn, "arguments", None) if fn else "{}",
            }
        )
    return {"content": (getattr(msg, "content", None) or "").strip(), "tool_calls": tool_calls}


async def chat(messages: list[dict[str, Any]], tools: list[dict] | None = None) -> dict[str, Any]:
    s = get_settings()
    kwargs: dict[str, Any] = {
        "model": s.ollama_model,
        "messages": messages,
        "temperature": 0.2,
    }
    if tools:
        kwargs["tools"] = tools
        kwargs["tool_choice"] = "auto"
    tools_stripped = False
    try:
        resp = await client().chat.completions.create(**kwargs)
    except Exception:
        kwargs.pop("tools", None)
        kwargs.pop("tool_choice", None)
        tools_stripped = bool(tools)
        resp = await client().chat.completions.create(**kwargs)
    choices = getattr(resp, "choices", None) or []
    if not choices:
        return {"content": "", "tool_calls": [], "tools_stripped": tools_stripped}
    parsed = _parse_message(choices[0].message)
    parsed["tools_stripped"] = tools_stripped
    return parsed


async def ping() -> tuple[bool, str]:
    s = get_settings()
    try:
        await client().models.list()
        return True, s.ollama_model
    except Exception as exc:
        return False, str(exc)

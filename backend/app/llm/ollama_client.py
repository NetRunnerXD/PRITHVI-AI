from __future__ import annotations

from contextvars import ContextVar
from typing import Any

from openai import AsyncOpenAI

from app.config import get_settings
from app.llm import providers as registry
from app.llm.worker_hub import WorkerOffline, hub

_clients: dict[str, AsyncOpenAI] = {}
_active: ContextVar[str | None] = ContextVar("llm_provider", default=None)


def use_provider(pid: str | None):
    return _active.set((pid or "").strip().lower() or None)


def reset_provider(token) -> None:
    _active.reset(token)


def _resolved():
    return registry.resolve(_active.get())


def client() -> AsyncOpenAI:
    p = _resolved()
    hit = _clients.get(p.id)
    if hit is None:
        kwargs: dict[str, Any] = {"base_url": p.base_url, "api_key": p.api_key or "none", "timeout": 120.0}
        if p.id == "openrouter":
            kwargs["default_headers"] = {"HTTP-Referer": "https://rituchakra.local", "X-Title": "Rituchakra"}
        hit = AsyncOpenAI(**kwargs)
        _clients[p.id] = hit
    return hit


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


def _order() -> list[str]:
    primary = _resolved()
    ids = [primary.id]
    for fid in registry.fallback_ids():
        if fid not in ids:
            ids.append(fid)
    return ids


async def chat(
    messages: list[dict[str, Any]],
    tools: list[dict] | None = None,
    *,
    model: str | None = None,
) -> dict[str, Any]:
    last_err: Exception | None = None
    for pid in _order():
        p = registry.spec(pid)
        if p is None or not p.keyed:
            continue
        tok = _active.set(pid)
        try:
            kwargs: dict[str, Any] = {
                "model": model or p.model,
                "messages": messages,
                "temperature": 0.2,
            }
            if tools:
                kwargs["tools"] = tools
                kwargs["tool_choice"] = "auto"
            tools_stripped = False
            if pid == "ollama" and hub.online():
                try:
                    parsed = await hub.submit(kwargs, timeout=float(get_settings().llm_worker_timeout_s))
                except WorkerOffline as exc:
                    last_err = exc
                    continue
                parsed = {
                    "content": (parsed.get("content") or "").strip(),
                    "tool_calls": parsed.get("tool_calls") or [],
                    "tools_stripped": bool(parsed.get("tools_stripped")),
                    "provider": pid,
                    "via": "home-worker",
                }
                return parsed
            try:
                resp = await client().chat.completions.create(**kwargs)
            except Exception:
                kwargs.pop("tools", None)
                kwargs.pop("tool_choice", None)
                tools_stripped = bool(tools)
                resp = await client().chat.completions.create(**kwargs)
            choices = getattr(resp, "choices", None) or []
            if not choices:
                return {"content": "", "tool_calls": [], "tools_stripped": tools_stripped, "provider": pid}
            parsed = _parse_message(choices[0].message)
            parsed["tools_stripped"] = tools_stripped
            parsed["provider"] = pid
            return parsed
        except Exception as exc:
            last_err = exc
            continue
        finally:
            _active.reset(tok)
    return {
        "content": "",
        "tool_calls": [],
        "tools_stripped": bool(tools),
        "provider": _resolved().id,
        "error": str(last_err or "no provider"),
    }


async def ping() -> tuple[bool, str]:
    """Local Ollama liveness only. Hosted keys are not probed (no quota burn)."""
    s = get_settings()
    p = _resolved()
    if p.id != "ollama":
        return True, f"{p.id}:{p.model}"
    if hub.online():
        return True, f"home-online:{p.model}"
    try:
        await client().models.list()
        return True, p.model
    except Exception as exc:
        token = (s.llm_worker_token or "").strip()
        if token:
            return False, "home-offline"
        return False, str(exc)


def catalog() -> dict[str, Any]:
    s = get_settings()
    active = registry.resolve(_active.get())
    rows = []
    for p in registry.available(s):
        rows.append({"id": p.id, "model": p.model, "ok": True})
    home = hub.status()
    return {
        "active": active.id,
        "model": active.model,
        "available": rows,
        "ollama": {
            "ok": True,
            "model": s.ollama_model,
            "home": home,
        },
    }

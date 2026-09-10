from __future__ import annotations

import copy
from contextvars import ContextVar
from typing import Any

from openai import AsyncOpenAI

from app.config import get_settings
from app.llm import providers as registry
from app.llm.worker_hub import WorkerOffline, hub

_TOOL_XML_HINT = (
    "Call tools via the API tool_calls field only. "
    "Never write XML such as <function= or a prose data: line."
)

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
    content = (getattr(msg, "content", None) or "").strip()
    if not tool_calls and content:
        from app.agents.data_tool import parse_xml_tool_calls

        xml = parse_xml_tool_calls(content)
        if xml:
            tool_calls = xml
            content = ""
    return {"content": content, "tool_calls": tool_calls}


def _exc_kind(exc: BaseException) -> str:
    status = getattr(exc, "status_code", None)
    resp = getattr(exc, "response", None)
    body = ""
    if resp is not None:
        status = status or getattr(resp, "status_code", None)
        try:
            body = str(getattr(resp, "text", None) or getattr(resp, "content", "") or "")
        except Exception:
            body = ""
    blob = f"{exc} {body}".lower()
    code = 0
    try:
        code = int(status) if status is not None else 0
    except (TypeError, ValueError):
        code = 0
    if code == 429 or "rate limit" in blob or "too many requests" in blob:
        return "rate"
    if code >= 500:
        return "server"
    if "tool_use_failed" in blob or "failed to call a function" in blob:
        return "tool_use"
    if code == 400 or "invalid_request" in blob or "schema" in blob:
        return "schema"
    return "other"


def _short_err(exc: BaseException) -> str:
    return str(exc).replace("\n", " ")[:160]


def _failed_generation(exc: BaseException) -> str:
    body = getattr(exc, "body", None)
    if isinstance(body, dict):
        err = body.get("error")
        if isinstance(err, dict):
            return str(err.get("failed_generation") or "")
        if isinstance(err, str) and "<function" in err:
            return err
    resp = getattr(exc, "response", None)
    if resp is not None:
        try:
            data = resp.json() if callable(getattr(resp, "json", None)) else None
            if isinstance(data, dict):
                err = data.get("error") or {}
                if isinstance(err, dict):
                    return str(err.get("failed_generation") or "")
        except Exception:
            pass
    text = str(exc)
    if "<function" in text:
        return text
    return ""


def _salvage_tool_calls(exc: BaseException) -> list[dict[str, Any]]:
    from app.agents.data_tool import parse_xml_tool_calls

    return parse_xml_tool_calls(_failed_generation(exc))


def sanitize_tools(tools: list[dict[str, Any]] | None) -> list[dict[str, Any]] | None:
    if not tools:
        return tools
    out = copy.deepcopy(tools)
    for t in out:
        params = (t.get("function") or {}).get("parameters")
        if isinstance(params, dict):
            params["additionalProperties"] = False
            params.setdefault("type", "object")
    return out


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
            hosted = pid in ("groq", "gemini", "openrouter", "xai", "github")
            if tools:
                kwargs["tools"] = sanitize_tools(tools) if hosted else tools
                kwargs["tool_choice"] = "auto"
            tools_stripped = False
            strip_err = ""
            use_hub = pid == "worker" or (pid == "ollama" and hub.online())
            if pid == "local":
                use_hub = False
            if use_hub:
                if pid == "worker" and not hub.online():
                    last_err = WorkerOffline("home ollama offline")
                    continue
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
            api = client()
            try:
                resp = await api.chat.completions.create(**kwargs)
            except Exception as exc:
                kind = _exc_kind(exc)
                if kind in ("rate", "server"):
                    last_err = exc
                    continue
                if tools and kind == "tool_use":
                    salvaged = _salvage_tool_calls(exc)
                    if salvaged:
                        return {
                            "content": "",
                            "tool_calls": salvaged,
                            "tools_stripped": False,
                            "provider": pid,
                            "via": "failed-generation",
                        }
                    nudged = dict(kwargs)
                    nudged["messages"] = list(messages) + [{"role": "system", "content": _TOOL_XML_HINT}]
                    try:
                        resp = await api.chat.completions.create(**nudged)
                    except Exception as exc2:
                        salvaged = _salvage_tool_calls(exc2)
                        if salvaged:
                            return {
                                "content": "",
                                "tool_calls": salvaged,
                                "tools_stripped": False,
                                "provider": pid,
                                "via": "failed-generation",
                            }
                        kind = _exc_kind(exc2)
                        if kind in ("rate", "server"):
                            last_err = exc2
                            continue
                        kwargs.pop("tools", None)
                        kwargs.pop("tool_choice", None)
                        tools_stripped = True
                        strip_err = _short_err(exc2)
                        resp = await api.chat.completions.create(**kwargs)
                elif tools and kind in ("schema", "other"):
                    try:
                        retry_kw = dict(kwargs)
                        retry_kw["tools"] = sanitize_tools(tools)
                        resp = await api.chat.completions.create(**retry_kw)
                    except Exception as exc2:
                        kind2 = _exc_kind(exc2)
                        if kind2 in ("rate", "server"):
                            last_err = exc2
                            continue
                        kwargs.pop("tools", None)
                        kwargs.pop("tool_choice", None)
                        tools_stripped = True
                        strip_err = _short_err(exc)
                        resp = await api.chat.completions.create(**kwargs)
                else:
                    raise
            choices = getattr(resp, "choices", None) or []
            if not choices:
                out = {"content": "", "tool_calls": [], "tools_stripped": tools_stripped, "provider": pid}
                if strip_err:
                    out["error"] = strip_err
                return out
            parsed = _parse_message(choices[0].message)
            parsed["tools_stripped"] = tools_stripped
            parsed["provider"] = pid
            if strip_err:
                parsed["error"] = strip_err
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
    """Prefer local Ollama. Groq is fallback liveness only after local probe fails."""
    s = get_settings()
    p = _resolved()
    if p.id not in ("ollama", "local", "worker"):
        return True, f"{p.id}:{p.model}"
    if p.id == "worker":
        if hub.online():
            return True, f"home-online:{p.model}"
        return False, "home-offline"
    if p.id != "local" and hub.online():
        return True, f"home-online:{p.model}"
    try:
        from app.providers.http import client as http_client

        base = (p.base_url or "").rstrip("/")
        r = await http_client().get(f"{base}/models", headers={"Authorization": f"Bearer {p.api_key or 'ollama'}"})
        if r.status_code < 400:
            return True, p.model
        raise RuntimeError(f"ollama-http-{r.status_code}")
    except Exception as local_exc:
        groq = registry.spec("groq", s)
        if groq and groq.keyed:
            try:
                from app.providers.http import client as http_client

                r = await http_client().get(
                    "https://api.groq.com/openai/v1/models",
                    headers={"Authorization": f"Bearer {groq.api_key}"},
                )
                if r.status_code < 400:
                    return True, f"groq-fallback:{groq.model}"
            except Exception:
                pass
        token = (s.llm_worker_token or "").strip()
        if token:
            return False, "home-offline"
        return False, str(local_exc)[:160]


def catalog() -> dict[str, Any]:
    s = get_settings()
    active = registry.resolve(_active.get())
    home = hub.status()
    choices = []
    for pid in registry.SETTINGS_IDS:
        p = registry.spec(pid, s)
        if p is None:
            continue
        ok = bool(p.keyed)
        reason = ""
        if pid == "worker":
            ok = bool(p.keyed and home.get("online"))
            reason = "" if ok else ("no worker token" if not p.keyed else "home PC worker offline")
        elif pid == "local":
            ok = True
            reason = "this machine Ollama"
        elif pid in ("groq", "gemini") and not p.keyed:
            reason = "no API key on server"
        choices.append({"id": pid, "model": p.model, "ok": ok, "reason": reason})
    rows = list(choices)
    for p in registry.available(s):
        if p.id not in {c["id"] for c in rows}:
            rows.append({"id": p.id, "model": p.model, "ok": True})
    return {
        "active": active.id,
        "model": active.model,
        "available": rows,
        "settings": choices,
        "ollama": {
            "ok": True,
            "model": s.ollama_model,
            "home": home,
        },
        "groq": {
            "keyed": bool((s.groq_api_key or "").strip()),
            "model": s.groq_model,
        },
    }

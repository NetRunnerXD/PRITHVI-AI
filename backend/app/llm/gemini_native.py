"""Gemini generateContent REST. OpenAI-shaped messages in, OpenAI-shaped tool_calls out."""

from __future__ import annotations

import json
from typing import Any

import httpx

_SAFETY = [
    {"category": c, "threshold": "BLOCK_NONE"}
    for c in (
        "HARM_CATEGORY_HARASSMENT",
        "HARM_CATEGORY_HATE_SPEECH",
        "HARM_CATEGORY_SEXUALLY_EXPLICIT",
        "HARM_CATEGORY_DANGEROUS_CONTENT",
    )
]

_http: httpx.AsyncClient | None = None


def _http_client() -> httpx.AsyncClient:
    global _http
    if _http is None:
        _http = httpx.AsyncClient(timeout=httpx.Timeout(45.0, connect=10.0))
    return _http


def _parse_args(raw: Any) -> dict[str, Any]:
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str) and raw.strip():
        try:
            data = json.loads(raw)
            return data if isinstance(data, dict) else {}
        except json.JSONDecodeError:
            return {}
    return {}


def _fn_parts(parts: list[dict[str, Any]]) -> bool:
    return any("functionCall" in p or "functionResponse" in p for p in parts)


def openai_tools_to_gemini(tools: list[dict[str, Any]] | None) -> list[dict[str, Any]] | None:
    if not tools:
        return None
    decls = []
    for t in tools:
        fn = t.get("function") or t
        name = fn.get("name")
        if not name:
            continue
        params = dict(fn.get("parameters") or {"type": "object", "properties": {}})
        params.pop("additionalProperties", None)
        decls.append(
            {
                "name": name,
                "description": fn.get("description") or "",
                "parameters": params,
            }
        )
    if not decls:
        return None
    return [{"functionDeclarations": decls}]


def openai_messages_to_gemini(messages: list[dict[str, Any]]) -> tuple[str, list[dict[str, Any]]]:
    system: list[str] = []
    contents: list[dict[str, Any]] = []
    pending_names: list[str] = []
    for m in messages:
        role = (m.get("role") or "user").strip().lower()
        text = (m.get("content") or "") if isinstance(m.get("content"), str) else str(m.get("content") or "")
        if role == "system":
            if text.strip():
                system.append(text.strip())
            continue
        if role == "tool":
            try:
                parsed = json.loads(text) if text.strip().startswith(("{", "[")) else {"text": text}
            except json.JSONDecodeError:
                parsed = {"text": text[:8000]}
            if not isinstance(parsed, dict):
                parsed = {"result": parsed}
            name = pending_names.pop(0) if pending_names else "data"
            contents.append(
                {"role": "user", "parts": [{"functionResponse": {"name": name, "response": parsed}}]}
            )
            continue
        if role == "assistant":
            parts: list[dict[str, Any]] = []
            if text.strip():
                parts.append({"text": text})
            names: list[str] = []
            for tc in m.get("tool_calls") or []:
                fn = tc.get("function") or tc
                args = _parse_args(fn.get("arguments") or tc.get("arguments"))
                name = fn.get("name") or tc.get("name") or "data"
                names.append(name)
                parts.append({"functionCall": {"name": name, "args": args}})
            if names:
                pending_names.extend(names)
            if parts:
                contents.append({"role": "model", "parts": parts})
            continue
        contents.append({"role": "user", "parts": [{"text": text}]})

    merged: list[dict[str, Any]] = []
    for c in contents:
        if (
            merged
            and merged[-1]["role"] == c["role"]
            and not _fn_parts(merged[-1]["parts"])
            and not _fn_parts(c["parts"])
        ):
            merged[-1]["parts"].extend(c["parts"])
        else:
            merged.append({"role": c["role"], "parts": list(c["parts"])})
    if merged and merged[0]["role"] == "model" and not _fn_parts(merged[0]["parts"]):
        merged.insert(0, {"role": "user", "parts": [{"text": "(continue)"}]})
    if not merged:
        merged = [{"role": "user", "parts": [{"text": "Hello"}]}]
    return "\n\n".join(system), merged


def parse_gemini_response(body: dict[str, Any]) -> dict[str, Any]:
    cands = body.get("candidates") or []
    if not cands:
        reason = ""
        fb = body.get("promptFeedback") or {}
        if isinstance(fb, dict):
            reason = str(fb.get("blockReason") or fb.get("block_reason") or "")
        raise RuntimeError(reason or "gemini empty candidates")
    cand = cands[0] if isinstance(cands[0], dict) else {}
    content = cand.get("content") or {}
    parts = content.get("parts") or []
    texts: list[str] = []
    tool_calls: list[dict[str, Any]] = []
    for i, part in enumerate(parts):
        if not isinstance(part, dict):
            continue
        if part.get("thought"):
            continue
        if part.get("text"):
            texts.append(str(part["text"]))
        fc = part.get("functionCall") or part.get("function_call")
        if isinstance(fc, dict) and fc.get("name"):
            args = fc.get("args") if isinstance(fc.get("args"), dict) else _parse_args(fc.get("args"))
            tool_calls.append(
                {
                    "id": f"g{i}",
                    "name": fc.get("name"),
                    "arguments": json.dumps(args, ensure_ascii=False),
                }
            )
    blob = "\n".join(texts).strip()
    if not tool_calls and blob:
        from app.agents.data_tool import parse_xml_tool_calls

        xml = parse_xml_tool_calls(blob)
        if xml:
            tool_calls = xml
            blob = ""
    return {"content": blob, "tool_calls": tool_calls}


def build_payload(
    messages: list[dict[str, Any]],
    *,
    tools: list[dict[str, Any]] | None = None,
    max_tokens: int = 512,
    thinking_level: str = "minimal",
) -> dict[str, Any]:
    """Gemini 3.x: narration only. No functionDeclarations; thinkingLevel minimal."""
    sys_text, contents = openai_messages_to_gemini(messages)
    payload: dict[str, Any] = {
        "contents": contents,
        "generationConfig": {
            "maxOutputTokens": max_tokens,
            "thinkingConfig": {"thinkingLevel": thinking_level},
        },
        "safetySettings": _SAFETY,
    }
    if sys_text:
        payload["systemInstruction"] = {"parts": [{"text": sys_text}]}
    return payload


async def generate(
    *,
    api_key: str,
    model: str,
    messages: list[dict[str, Any]],
    tools: list[dict[str, Any]] | None = None,
    temperature: float = 0.2,
    max_tokens: int = 512,
) -> dict[str, Any]:
    payload = build_payload(messages, tools=None, max_tokens=max_tokens)
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
    r = await _http_client().post(
        url,
        headers={"x-goog-api-key": api_key, "Content-Type": "application/json"},
        json=payload,
    )
    if r.status_code >= 400:
        raise RuntimeError(f"gemini-http-{r.status_code} {r.text[:240]}")
    data = r.json()
    if not isinstance(data, dict):
        raise RuntimeError("gemini bad json")
    parsed = parse_gemini_response(data)
    parsed["provider"] = "gemini"
    parsed["via"] = "generateContent"
    parsed["tools_stripped"] = False
    return parsed

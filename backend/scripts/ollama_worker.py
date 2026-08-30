"""Connect this PC's Ollama to a deployed PRITHVI-AI API.

The cloud host cannot dial into NAT. This process opens an outbound WebSocket,
runs chat.completions against local Ollama, and posts results back.

  set LLM_WORKER_TOKEN=...   (same value as the cloud env)
  set PRITHVI_API=https://your-api.example
  python scripts/ollama_worker.py

Ollama must already be serving on this machine (`ollama serve`).
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from typing import Any

import httpx

try:
    import websockets
except ImportError:  # pragma: no cover
    print("Install websockets (comes with uvicorn[standard]).", file=sys.stderr)
    raise


def _ws_url(api: str) -> str:
    base = api.rstrip("/")
    if base.startswith("https://"):
        return "wss://" + base[len("https://") :] + "/api/llm/worker"
    if base.startswith("http://"):
        return "ws://" + base[len("http://") :] + "/api/llm/worker"
    return "ws://" + base + "/api/llm/worker"


async def _complete(ollama: str, key: str, job: dict[str, Any]) -> dict[str, Any]:
    url = ollama.rstrip("/") + "/chat/completions"
    body: dict[str, Any] = {
        "model": job.get("model"),
        "messages": job.get("messages") or [],
        "temperature": job.get("temperature", 0.2),
        "stream": False,
    }
    if job.get("tools"):
        body["tools"] = job["tools"]
        body["tool_choice"] = job.get("tool_choice") or "auto"
    headers = {"Authorization": f"Bearer {key or 'ollama'}"}
    stripped = False
    async with httpx.AsyncClient(timeout=120.0) as client:
        try:
            r = await client.post(url, json=body, headers=headers)
            r.raise_for_status()
        except Exception:
            body.pop("tools", None)
            body.pop("tool_choice", None)
            stripped = bool(job.get("tools"))
            r = await client.post(url, json=body, headers=headers)
            r.raise_for_status()
    data = r.json()
    choices = data.get("choices") or []
    msg = (choices[0].get("message") if choices else {}) or {}
    calls = []
    for c in msg.get("tool_calls") or []:
        fn = c.get("function") or {}
        calls.append({"id": c.get("id") or "call", "name": fn.get("name"), "arguments": fn.get("arguments") or "{}"})
    return {
        "type": "result",
        "id": job.get("id"),
        "content": (msg.get("content") or "").strip(),
        "tool_calls": calls,
        "tools_stripped": stripped,
    }


HINT_403 = (
    "HTTP 403 usually means this API build has no /api/llm/worker route "
    "(old Render deploy) or the WebSocket was refused before auth. "
    "Push the latest backend, set LLM_WORKER_TOKEN on Render to the same "
    "value as this PC, then restart the Render service."
)


async def _preflight(api: str) -> None:
    base = api.rstrip("/")
    url = base + "/api/llm/home"
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            r = await client.get(url)
    except Exception as exc:
        print(f"preflight failed {url} ({exc})", flush=True)
        return
    if r.status_code == 404:
        print(
            "preflight: GET /api/llm/home is 404 — Render is still on an old API. "
            "Deploy the current backend (worker hub), then set LLM_WORKER_TOKEN there.",
            flush=True,
        )
        return
    if r.status_code != 200:
        print(f"preflight: {url} -> {r.status_code} {r.text[:200]}", flush=True)
        return
    try:
        data = r.json()
    except Exception:
        print(f"preflight: {url} not JSON", flush=True)
        return
    if not data.get("configured"):
        print(
            "preflight: API has the worker route but LLM_WORKER_TOKEN is empty on the server. "
            "Render → Environment → add LLM_WORKER_TOKEN (same as this PC) → Restart.",
            flush=True,
        )
        return
    print(
        f"preflight: API worker route ok (configured, online={data.get('online')})",
        flush=True,
    )


async def run(api: str, token: str, ollama: str, key: str) -> None:
    await _preflight(api)
    url = _ws_url(api) + f"?token={token}"
    origin = api.rstrip("/")
    print(f"worker connecting {url.split('?')[0]} → {ollama}", flush=True)
    backoff = 1.0
    extra = {"Origin": origin, "User-Agent": "prithvi-ollama-worker/1"}
    while True:
        try:
            async with websockets.connect(
                url,
                ping_interval=20,
                ping_timeout=20,
                additional_headers=extra,
            ) as ws:
                backoff = 1.0
                print("worker online", flush=True)
                await ws.send(json.dumps({"type": "hello"}))
                async for raw in ws:
                    try:
                        data = json.loads(raw)
                    except json.JSONDecodeError:
                        continue
                    kind = data.get("type")
                    if kind == "error" and not data.get("id"):
                        print(f"server: {data.get('error')}", flush=True)
                        continue
                    if kind == "job":
                        try:
                            out = await _complete(ollama, key, data)
                        except Exception as exc:
                            out = {"type": "error", "id": data.get("id"), "error": str(exc)}
                        await ws.send(json.dumps(out))
                    elif kind == "ping":
                        await ws.send(json.dumps({"type": "pong"}))
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            msg = str(exc)
            if "403" in msg:
                msg = f"{msg} — {HINT_403}"
            print(f"worker reconnect in {backoff:.0f}s ({msg})", flush=True)
            await asyncio.sleep(backoff)
            backoff = min(30.0, backoff * 2)


def main() -> int:
    p = argparse.ArgumentParser(description="PRITHVI-AI home Ollama worker")
    p.add_argument("--api", default=os.environ.get("PRITHVI_API") or os.environ.get("PUBLIC_BASE_URL") or "http://127.0.0.1:8000")
    p.add_argument("--token", default=os.environ.get("LLM_WORKER_TOKEN") or "")
    p.add_argument("--ollama", default=os.environ.get("OLLAMA_BASE_URL") or "http://127.0.0.1:11434/v1")
    p.add_argument("--key", default=os.environ.get("OLLAMA_API_KEY") or "ollama")
    args = p.parse_args()
    if not args.token.strip():
        print("Set LLM_WORKER_TOKEN (must match the deployed API).", file=sys.stderr)
        return 2
    asyncio.run(run(args.api, args.token.strip(), args.ollama, args.key))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

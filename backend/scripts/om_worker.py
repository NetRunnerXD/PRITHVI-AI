"""Relay Open-Meteo fetches from this machine's IP to a deployed API.

The cloud host is often 429'd (shared Render IP). This process opens an
outbound WebSocket and GETs allowlisted Open-Meteo URLs locally.

  set LLM_WORKER_TOKEN=...   (same value as the cloud env)
  set PRITHVI_API=https://rituchakra-api.onrender.com
  python scripts/om_worker.py
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
from typing import Any
from urllib.parse import urlparse

import httpx

try:
    import websockets
except ImportError:  # pragma: no cover
    print("Install websockets (comes with uvicorn[standard]).", file=sys.stderr)
    raise

ALLOW = (
    "api.open-meteo.com",
    "flood-api.open-meteo.com",
    "air-quality-api.open-meteo.com",
    "marine-api.open-meteo.com",
    "archive-api.open-meteo.com",
    "geocoding-api.open-meteo.com",
    "customer-api.open-meteo.com",
    "customer-flood-api.open-meteo.com",
    "customer-air-quality-api.open-meteo.com",
    "customer-marine-api.open-meteo.com",
    "customer-archive-api.open-meteo.com",
    "customer-geocoding-api.open-meteo.com",
)


def _ws_url(api: str) -> str:
    base = api.rstrip("/")
    if base.startswith("https://"):
        return "wss://" + base[len("https://") :] + "/api/om/worker"
    if base.startswith("http://"):
        return "ws://" + base[len("http://") :] + "/api/om/worker"
    return "ws://" + base + "/api/om/worker"


def _ok_url(url: str) -> bool:
    try:
        u = urlparse(url)
    except Exception:
        return False
    if u.scheme not in {"http", "https"}:
        return False
    host = (u.hostname or "").lower()
    return host in ALLOW and (u.path or "").startswith("/v1/")


async def _fetch(url: str, params: dict[str, Any] | None) -> dict[str, Any]:
    if not _ok_url(url):
        raise RuntimeError("url not allowlisted")
    async with httpx.AsyncClient(timeout=25.0) as client:
        r = await client.get(url, params=params or None)
        r.raise_for_status()
        data = r.json()
        if not isinstance(data, (dict, list)):
            raise RuntimeError("non-json")
        return data  # type: ignore[return-value]


async def run(api: str, token: str) -> None:
    url = _ws_url(api)
    q = f"{url}?token={token}"
    print(f"om-relay connecting {url}", flush=True)
    async with websockets.connect(q, ping_interval=20, ping_timeout=20, max_size=8_000_000) as ws:
        print("om-relay online", flush=True)
        async for raw in ws:
            try:
                import json

                msg = json.loads(raw)
            except Exception:
                continue
            if (msg or {}).get("type") != "fetch":
                continue
            jid = msg.get("id")
            try:
                body = await _fetch(str(msg.get("url") or ""), msg.get("params") if isinstance(msg.get("params"), dict) else None)
                await ws.send(json.dumps({"type": "result", "id": jid, "json": body}))
            except Exception as exc:
                await ws.send(json.dumps({"type": "error", "id": jid, "error": str(exc)[:240]}))


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--api", default=os.environ.get("PRITHVI_API") or "http://127.0.0.1:8000")
    p.add_argument("--token", default=os.environ.get("OM_WORKER_TOKEN") or os.environ.get("LLM_WORKER_TOKEN") or "")
    args = p.parse_args()
    if not args.token:
        print("Set LLM_WORKER_TOKEN (must match the deployed API).", file=sys.stderr)
        sys.exit(2)
    try:
        asyncio.run(run(args.api, args.token))
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()

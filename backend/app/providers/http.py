from __future__ import annotations

import httpx

from app.config import get_settings

_client: httpx.AsyncClient | None = None


def client() -> httpx.AsyncClient:
    global _client
    if _client is None:
        settings = get_settings()
        _client = httpx.AsyncClient(
            timeout=httpx.Timeout(25.0, connect=8.0),
            headers={"User-Agent": settings.user_agent, "Accept": "application/json, application/xml, text/xml, */*"},
            follow_redirects=True,
        )
    return _client


async def aclose() -> None:
    global _client
    if _client is None:
        return
    try:
        await _client.aclose()
    except RuntimeError:
        pass
    _client = None

"""Shared outbound HTTP client.

One pooled AsyncClient for every provider: keep-alive, HTTP/2 where the server offers it
(ALPN; falls back to 1.1), a tight default timeout, bounded retry with exponential
backoff + jitter on 429/502/503/504 for idempotent requests, and a per-host circuit
breaker so a dead upstream fails fast instead of eating every request's time budget.
"""

from __future__ import annotations

import asyncio
import random
import time
from typing import Any

import httpx

from app.config import get_settings

_client: httpx.AsyncClient | None = None

RETRY_STATUS = {429, 502, 503, 504}
MAX_RETRIES = 2
BREAKER_FAILS = 5  # consecutive failures that open the breaker
BREAKER_OPEN_S = 30.0


class _Breaker:
    __slots__ = ("fails", "open_until")

    def __init__(self) -> None:
        self.fails = 0
        self.open_until = 0.0


_breakers: dict[str, _Breaker] = {}


def breaker_state() -> dict[str, Any]:
    now = time.monotonic()
    return {h: {"fails": b.fails, "open": b.open_until > now} for h, b in _breakers.items()}


class ResilientTransport(httpx.AsyncBaseTransport):
    def __init__(self, inner: httpx.AsyncBaseTransport) -> None:
        self._inner = inner

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        host = request.url.host or ""
        br = _breakers.setdefault(host, _Breaker())
        now = time.monotonic()
        if br.open_until > now:
            raise httpx.ConnectError(f"circuit open for {host} ({br.open_until - now:.0f}s)", request=request)
        idempotent = request.method in {"GET", "HEAD", "OPTIONS"}
        attempt = 0
        while True:
            try:
                resp = await self._inner.handle_async_request(request)
            except (httpx.ConnectError, httpx.ConnectTimeout, httpx.RemoteProtocolError) as e:
                if idempotent and attempt < 1:
                    attempt += 1
                    await asyncio.sleep(0.15 + random.random() * 0.2)
                    continue
                self._fail(br)
                raise e
            except httpx.TimeoutException:
                self._fail(br)
                raise
            if resp.status_code in RETRY_STATUS and idempotent and attempt < MAX_RETRIES:
                delay = min(2.0, 0.4 * (2**attempt)) * (0.5 + random.random())
                ra = resp.headers.get("retry-after")
                if ra and ra.isdigit():
                    if int(ra) > 3:  # do not park a request for long; let callers fall back
                        if resp.status_code >= 500:
                            self._fail(br)
                        return resp
                    delay = max(delay, float(ra))
                await resp.aclose()
                attempt += 1
                await asyncio.sleep(delay)
                continue
            if resp.status_code >= 500:
                self._fail(br)
            else:
                br.fails = 0
            return resp

    @staticmethod
    def _fail(br: _Breaker) -> None:
        br.fails += 1
        if br.fails >= BREAKER_FAILS:
            br.open_until = time.monotonic() + BREAKER_OPEN_S
            br.fails = 0

    async def aclose(self) -> None:
        await self._inner.aclose()


def _http2_available() -> bool:
    try:
        import h2  # noqa: F401
    except ImportError:
        return False
    return True


def client() -> httpx.AsyncClient:
    global _client
    if _client is None:
        settings = get_settings()
        limits = httpx.Limits(max_connections=60, max_keepalive_connections=30, keepalive_expiry=60.0)
        inner = httpx.AsyncHTTPTransport(http2=_http2_available(), limits=limits)
        _client = httpx.AsyncClient(
            transport=ResilientTransport(inner),
            timeout=httpx.Timeout(6.0, connect=2.0),
            headers={
                "User-Agent": settings.user_agent,
                "Accept": "application/json, application/xml, text/xml, */*",
                "Accept-Encoding": "gzip, deflate",
            },
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

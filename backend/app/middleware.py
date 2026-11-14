"""HTTP middlewares: JSON errors (inside CORS), Cache-Control defaults, selective gzip."""

from __future__ import annotations

import asyncio
import logging
from urllib.parse import parse_qsl

from starlette.datastructures import MutableHeaders
from starlette.middleware.gzip import GZipMiddleware
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send

log = logging.getLogger("prithvi.http")

# (path suffix after the /api|/v1|… prefix, Cache-Control). Public, location-keyed data only.
_CACHE_RULES: tuple[tuple[str, str], ...] = (
    ("/nowcast/storm-map", "public, max-age=60, stale-while-revalidate=240"),
    ("/cyclones", "public, max-age=300, stale-while-revalidate=900"),
    ("/sat/gibs/latest", "public, max-age=300, stale-while-revalidate=900"),
    ("/sat/imd-asia/meta", "public, max-age=120, stale-while-revalidate=600"),
    ("/nowcast/live", "public, max-age=60, stale-while-revalidate=300"),
    ("/nowcast/sat", "public, max-age=60, stale-while-revalidate=300"),
    ("/map/radar", "public, max-age=120, stale-while-revalidate=600"),
    ("/dashboard", "public, max-age=60, stale-while-revalidate=300"),
    ("/states", "public, max-age=86400"),
    ("/districts", "public, max-age=86400"),
    ("/ready", "no-store"),
)
_PREFIXES = ("/api", "/v1", "/web/v1", "/app/v1")


def _strip(path: str) -> str:
    for p in _PREFIXES:
        if path.startswith(p + "/"):
            return path[len(p) :]
    return path


def _leaked_cancel() -> bool:
    """True when a CancelledError reached us although *this* request task is not being
    cancelled (server shutdown / client disconnect set ``cancelling()``)."""
    task = asyncio.current_task()
    fn = getattr(task, "cancelling", None) if task is not None else None
    try:
        return not (fn() if callable(fn) else True)
    except Exception:
        return False


class JSONErrorMiddleware:
    """Pure ASGI: turn an unhandled exception into a JSON 500 and log the *real* traceback.

    BaseHTTPMiddleware stacking hid the inner error behind ``RuntimeError: No response
    returned`` (and a CancelledError from a shared provider fetch never reached it at all).
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope.get("type") != "http":
            await self.app(scope, receive, send)
            return
        started = False

        async def send_wrapper(message: Message) -> None:
            nonlocal started
            if message.get("type") == "http.response.start":
                started = True
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
            return
        except asyncio.CancelledError as e:
            if not _leaked_cancel():
                raise
            exc: BaseException = e
        except Exception as e:
            exc = e
        method = scope.get("method", "")
        path = scope.get("path", "")
        log.error("unhandled %s %s: %s", method, path, type(exc).__name__, exc_info=exc)
        if started:
            # Headers already went out; nothing valid we can append. Let the server close it.
            raise exc
        resp = JSONResponse(
            status_code=500,
            content={"ok": False, "error": "internal_error", "detail": type(exc).__name__},
        )
        await resp(scope, receive, send)


def _cache_value(method: str, status: int, path: str, query: str, headers: MutableHeaders) -> str | None:
    if method != "GET" or "cache-control" in headers:
        return None
    if status >= 400:
        return "no-store"
    flag = ""
    for k, v in parse_qsl(query or "", keep_blank_values=True):
        if k == "refresh":
            flag = (v or "").strip().lower()
            break
    if flag in {"1", "true", "yes", "on"}:
        return "no-store"
    sub = _strip(path)
    for suffix, value in _CACHE_RULES:
        if sub == suffix or sub.startswith(suffix + "?"):
            return value
    return None


class CacheControlMiddleware:
    """Pure ASGI Cache-Control defaults (only touches the response-start headers)."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope.get("type") != "http":
            await self.app(scope, receive, send)
            return
        method = scope.get("method", "")
        path = str(scope.get("path") or "")
        query = (scope.get("query_string") or b"").decode("latin-1")

        async def send_wrapper(message: Message) -> None:
            if message.get("type") == "http.response.start":
                headers = MutableHeaders(scope=message)
                value = _cache_value(method, int(message.get("status") or 200), path, query, headers)
                if value:
                    headers["Cache-Control"] = value
                    if value.startswith("public") and "vary" not in headers:
                        headers["Vary"] = "Accept-Encoding"
            await send(message)

        await self.app(scope, receive, send_wrapper)


class HeaderStampMiddleware:
    """Pure ASGI replacement for the old ``@app.middleware("http") stamp_version``."""

    def __init__(self, app: ASGIApp, version: str, surface) -> None:
        self.app = app
        self.version = version
        self.surface = surface

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope.get("type") != "http":
            await self.app(scope, receive, send)
            return
        path = str(scope.get("path") or "")
        client = None
        for k, v in scope.get("headers") or []:
            if k == b"x-rituchakra-client":
                client = v.decode("latin-1")
                break

        async def send_wrapper(message: Message) -> None:
            if message.get("type") == "http.response.start":
                headers = MutableHeaders(scope=message)
                headers["X-API-Version"] = self.version
                headers["X-Client-Surface"] = self.surface(path, client)
            await send(message)

        await self.app(scope, receive, send_wrapper)


class SelectiveGZipMiddleware:
    """gzip JSON/text, but never Server-Sent Events (gzip buffering breaks streaming)."""

    def __init__(self, app: ASGIApp, minimum_size: int = 1024) -> None:
        self.app = app
        self.gzip = GZipMiddleware(app, minimum_size=minimum_size)

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope.get("type") == "http":
            headers = dict(scope.get("headers") or [])
            accept = headers.get(b"accept", b"").decode("latin-1").lower()
            path = str(scope.get("path") or "")
            if (
                "text/event-stream" in accept
                or path.endswith("/chat")
                or path.endswith("/device/turn")
                or "/stream" in path
            ):
                await self.app(scope, receive, send)
                return
            await self.gzip(scope, receive, send)
            return
        await self.app(scope, receive, send)

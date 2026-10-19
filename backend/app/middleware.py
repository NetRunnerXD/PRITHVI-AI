"""HTTP middlewares: JSON errors (inside CORS), Cache-Control defaults, selective gzip."""

from __future__ import annotations

import logging

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.middleware.gzip import GZipMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send

log = logging.getLogger("prithvi.http")

# (path suffix after the /api|/v1|… prefix, Cache-Control). Public, location-keyed data only.
_CACHE_RULES: tuple[tuple[str, str], ...] = (
    ("/nowcast/storm-map", "public, max-age=60, stale-while-revalidate=240"),
    ("/cyclones", "public, max-age=300, stale-while-revalidate=900"),
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


class JSONErrorMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        try:
            return await call_next(request)
        except Exception as e:  # pragma: no cover - exercised via test client
            log.exception("unhandled %s %s", request.method, request.url.path)
            return JSONResponse(
                status_code=500,
                content={"ok": False, "error": "internal_error", "detail": type(e).__name__},
            )


class CacheControlMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        resp = await call_next(request)
        if request.method != "GET" or "cache-control" in resp.headers:
            return resp
        if resp.status_code >= 400:
            resp.headers["Cache-Control"] = "no-store"
            return resp
        sub = _strip(request.url.path)
        for suffix, value in _CACHE_RULES:
            if sub == suffix or sub.startswith(suffix + "?"):
                resp.headers["Cache-Control"] = value
                if value.startswith("public"):
                    resp.headers.setdefault("Vary", "Accept-Encoding")
                break
        return resp


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
            if "text/event-stream" in accept or path.endswith("/chat") or "/stream" in path:
                await self.app(scope, receive, send)
                return
            await self.gzip(scope, receive, send)
            return
        await self.app(scope, receive, send)

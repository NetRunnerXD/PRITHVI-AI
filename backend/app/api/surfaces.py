"""Mount the same JSON API under several prefixes.

Local Next.js, pytest, and clients/js keep using /api/*.
A published host can also serve /v1, /web/v1, and /app/v1 at the same time.
Aliases are omitted from OpenAPI so /docs stays a single contract.
"""

from fastapi import FastAPI, APIRouter

from app.api import chat, dashboard, geo, llm_worker, meta, speech
from app.auth.router import router as auth_router

# (prefix, surface id, include in OpenAPI)
MOUNTS: list[tuple[str, str, bool]] = [
    ("/api", "local", True),
    ("/v1", "v1", False),
    ("/web/v1", "web", False),
    ("/app/v1", "app", False),
]


def infer_surface(path: str, header: str | None = None) -> str:
    raw = (header or "").strip().lower()
    if raw in meta.SURFACES:
        return raw
    if path.startswith("/app/"):
        return "app"
    if path.startswith("/web/"):
        return "web"
    if path.startswith("/v1"):
        return "v1"
    return "local"


def _include(app: FastAPI, router: APIRouter, prefix: str, *, schema: bool, tags: list[str]) -> None:
    app.include_router(router, prefix=prefix, tags=tags, include_in_schema=schema)


def mount_surfaces(app: FastAPI) -> None:
    for prefix, _surface, schema in MOUNTS:
        _include(app, meta.router, prefix, schema=schema, tags=["meta"])
        _include(app, dashboard.router, prefix, schema=schema, tags=["snapshot"])
        _include(app, geo.router, prefix, schema=schema, tags=["geo"])
        _include(app, chat.router, prefix, schema=schema, tags=["advisor"])
        _include(app, llm_worker.router, prefix, schema=schema, tags=["llm"])
        _include(app, auth_router, prefix, schema=schema, tags=["account"])
        _include(app, speech.router, prefix, schema=schema, tags=["speech"])

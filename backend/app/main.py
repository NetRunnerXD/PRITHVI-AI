from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api import chat, dashboard, geo
from app.config import get_settings
from app.llm import ollama_client
from app.providers.http import aclose
from app.services.location_svc import resolve_location


@asynccontextmanager
async def lifespan(_: FastAPI):
    yield
    await aclose()


settings = get_settings()

app = FastAPI(
    title="Rituchakra API",
    version=settings.api_version,
    description=(
        "India-first environmental intelligence HTTP API. "
        "JSON only — no web assets. Any browser, Next.js, or React Native client "
        "can call these routes. The Advisor LLM never invents millimetres, litres, "
        "AQI, or rupees; those come from providers and models."
    ),
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    contact={"name": "Rituchakra"},
)

_cors_kwargs: dict = {
    "allow_methods": ["*"],
    "allow_headers": ["*"],
    "expose_headers": ["X-API-Version"],
}
if settings.cors_allow_all:
    _cors_kwargs["allow_origins"] = ["*"]
    _cors_kwargs["allow_credentials"] = False
else:
    _cors_kwargs["allow_origins"] = settings.cors_origin_list
    _cors_kwargs["allow_credentials"] = True
    if settings.cors_origin_regex:
        _cors_kwargs["allow_origin_regex"] = settings.cors_origin_regex
app.add_middleware(CORSMiddleware, **_cors_kwargs)

app.include_router(dashboard.router, prefix="/api", tags=["snapshot"])
app.include_router(geo.router, prefix="/api", tags=["geo"])
app.include_router(chat.router, prefix="/api", tags=["advisor"])


@app.middleware("http")
async def stamp_version(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-API-Version"] = settings.api_version
    return response


def _service_card() -> dict:
    return {
        "name": "Rituchakra",
        "service": "rituchakra-api",
        "version": settings.api_version,
        "ok": True,
        "docs": "/docs",
        "redoc": "/redoc",
        "openapi": "/openapi.json",
        "health": "/api/health",
        "catalog": "/api",
        "note": "Standalone JSON API. No frontend assets. Point a web or mobile client at this origin.",
    }


@app.get("/", tags=["meta"], summary="Service card")
async def root():
    return _service_card()


@app.get("/api", tags=["meta"], summary="Published route catalog")
async def api_catalog():
    routes: list[dict] = []
    for route in app.routes:
        methods = getattr(route, "methods", None)
        path = getattr(route, "path", None)
        if not methods or not path or not str(path).startswith("/api"):
            continue
        verb = sorted(m for m in methods if m not in {"HEAD", "OPTIONS"})
        if not verb:
            continue
        routes.append({"methods": verb, "path": path})
    routes.sort(key=lambda r: (r["path"], r["methods"]))
    return {**_service_card(), "routes": routes}


@app.get("/api/health", tags=["meta"], summary="Liveness")
async def health():
    ollama_ok, ollama_msg = await ollama_client.ping()
    loc = resolve_location()
    return {
        **_service_card(),
        "default_location": loc.model_dump(),
        "ollama": {"ok": ollama_ok, "detail": ollama_msg, "model": settings.ollama_model},
        "keys": {
            "imd_api_key": bool(settings.imd_api_key),
            "aikosh_api_key": bool(settings.aikosh_api_key),
            "data_gov_in_api_key": bool(settings.data_gov_in_api_key),
        },
        "notes": {
            "imd_rest": "api.imd.gov.in requires IP whitelist — CAP alerts are used until then.",
            "inject_keys": "See backend/.env.example",
            "clients": "Any origin allowed by CORS_ORIGINS / CORS_ORIGIN_REGEX. No Next.js rewrite required.",
        },
    }


@app.get("/api/ready", tags=["meta"], summary="Readiness")
async def ready():
    return JSONResponse({"ok": True, "service": "rituchakra-api", "version": settings.api_version})

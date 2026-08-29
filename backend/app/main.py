from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from app.api.meta import service_card
from app.api.surfaces import infer_surface, mount_surfaces
from app.config import get_settings
from app.providers.http import aclose


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
        "JSON only — no web assets. Canonical routes live under /api "
        "(local dashboard and tests). The same handlers are also served at "
        "/v1, /web/v1, and /app/v1 so a website and a phone app can call this "
        "process together. The Advisor LLM never invents millimetres, litres, "
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
    "expose_headers": ["X-API-Version", "X-Client-Surface"],
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

mount_surfaces(app)


@app.middleware("http")
async def stamp_version(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-API-Version"] = settings.api_version
    response.headers["X-Client-Surface"] = infer_surface(
        request.url.path,
        request.headers.get("x-rituchakra-client"),
    )
    return response


def _catalog_body() -> dict:
    routes: list[dict] = []
    for route in app.routes:
        methods = getattr(route, "methods", None)
        path = getattr(route, "path", None)
        if not methods or not path:
            continue
        p = str(path)
        if not (p.startswith("/api") or p.startswith("/v1") or p.startswith("/web/") or p.startswith("/app/")):
            continue
        verb = sorted(m for m in methods if m not in {"HEAD", "OPTIONS"})
        if not verb:
            continue
        routes.append({"methods": verb, "path": p})
    routes.sort(key=lambda r: (r["path"], r["methods"]))
    return {**service_card(), "routes": routes}


@app.get("/", tags=["meta"], summary="Service card")
async def root():
    return service_card()


@app.get("/api", tags=["meta"], summary="Published route catalog")
@app.get("/v1", tags=["meta"], summary="Versioned route catalog", include_in_schema=False)
@app.get("/web/v1", tags=["meta"], summary="Web surface catalog", include_in_schema=False)
@app.get("/app/v1", tags=["meta"], summary="App surface catalog", include_in_schema=False)
async def api_catalog():
    return _catalog_body()

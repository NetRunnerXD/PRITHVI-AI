from fastapi import APIRouter, Response
from fastapi.responses import JSONResponse

from app.config import get_settings
from app.llm import ollama_client
from app.llm.worker_hub import hub
from app.services.location_svc import resolve_location

router = APIRouter()
settings = get_settings()

# Local Next.js + tests keep /api. /v1 is the public contract.
# /web/v1 and /app/v1 are the same handlers for a website and a phone app
# hitting this process at once. Implementation is not duplicated.
SURFACES = {
    "local": {
        "prefix": "/api",
        "note": "Canonical routes. Local dashboard, pytest, clients/js default.",
    },
    "v1": {
        "prefix": "/v1",
        "note": "Stable public version of the same JSON API.",
    },
    "web": {
        "prefix": "/web/v1",
        "note": "Web front-end frameworks (Next, Vite, other browsers).",
    },
    "app": {
        "prefix": "/app/v1",
        "note": "Native / Expo / React Native. Same JSON as /web/v1.",
    },
}


def service_card() -> dict:
    return {
        "name": "Prithvi AI",
        "service": "prithvi-ai-api",
        "version": settings.api_version,
        "ok": True,
        "docs": "/docs",
        "redoc": "/redoc",
        "openapi": "/openapi.json",
        "health": "/api/health",
        "bootstrap": "/api/bootstrap",
        "catalog": "/api",
        "surfaces": SURFACES,
        "note": (
            "Standalone JSON API. No frontend assets. "
            "/api, /v1, /web/v1, and /app/v1 share one implementation. "
            "Point a web origin and a mobile origin at this host together."
        ),
    }


def capabilities() -> dict:
    return {
        "sse_chat": True,
        "json_chat": True,
        "storm_map": True,
        "nowcast_live": True,
        "geo_india_only": True,
        "concurrent_web_and_app": True,
    }


@router.head("/health", summary="Liveness probe")
async def health_head():
    return Response(status_code=200)


@router.get("/health", summary="Liveness")
async def health():
    ollama_ok, ollama_msg = await ollama_client.ping()
    loc = resolve_location()
    llm = ollama_client.catalog()
    llm["ollama"] = {
        "ok": ollama_ok,
        "detail": ollama_msg,
        "model": settings.ollama_model,
        "home": hub.status(),
    }
    llm["groq"] = {
        "keyed": bool((settings.groq_api_key or "").strip()),
        "model": settings.groq_model,
        "ok": bool(ollama_ok and str(ollama_msg).startswith("groq")),
    }
    llm["gemini"] = {
        "keyed": bool((settings.gemini_api_key or "").strip()),
        "model": settings.gemini_model,
        "ok": bool(ollama_ok and str(ollama_msg).startswith("gemini")),
    }
    return {
        **service_card(),
        "default_location": loc.model_dump(),
        "llm": llm,
        "ollama": {
            "ok": ollama_ok,
            "detail": ollama_msg,
            "model": settings.ollama_model,
            "home": hub.status(),
        },
        "keys": {
            "groq_api_key": bool((settings.groq_api_key or "").strip()),
            "gemini_api_key": bool((settings.gemini_api_key or "").strip()),
            "imd_api_key": bool(settings.imd_api_key),
            "aikosh_api_key": bool(settings.aikosh_api_key),
            "data_gov_in_api_key": bool(settings.data_gov_in_api_key),
            "weatherbit_api_key": bool(settings.weatherbit_api_key),
            "fast2sms_api_key": bool((settings.fast2sms_api_key or "").strip()),
        },
        "sms": {
            "enabled": bool(settings.sms_enabled),
            "dry_run": bool(settings.sms_dry_run),
            "has_key": bool((settings.fast2sms_api_key or "").strip()),
            "demo_to": f"+91 {(settings.sms_demo_to or '7439972482')}",
            "route": "q",
        },
        "notes": {
            "imd_rest": "api.imd.gov.in requires IP whitelist — CAP alerts are used until then.",
            "inject_keys": "See backend/.env.example",
            "clients": (
                "Web and app may call this origin together. "
                "CORS_ORIGINS / CORS_ORIGIN_REGEX list both. No Next.js rewrite required."
            ),
        },
    }


@router.get("/ready", summary="Readiness")
async def ready():
    body = {"ok": True, "service": "prithvi-ai-api", "version": settings.api_version, "role": settings.app_role}
    try:
        from app.store import ingest_status

        body["ingest"] = ingest_status.snapshot()
    except Exception:
        pass
    return JSONResponse(body)


@router.api_route("/ingest/trigger", methods=["GET", "POST"], summary="Trigger one satellite ingest & hazard crunching cycle via Cron")
async def trigger_ingest(secret: str | None = None, background: bool = False):
    s = get_settings()
    if s.ingest_cron_secret and secret != s.ingest_cron_secret:
        return JSONResponse({"ok": False, "error": "Unauthorized secret"}, status_code=401)
    from app.ingest.cycle import run_cycle
    import asyncio

    if background:
        asyncio.create_task(run_cycle())
        return JSONResponse({"ok": True, "status": "started_in_background"})

    result = await run_cycle()
    return JSONResponse(result)


@router.get("/bootstrap", summary="Client boot pack")
async def bootstrap():
    """First request for web or Android: pin, locales, flags, and route map."""
    ollama_ok, ollama_msg = await ollama_client.ping()
    loc = resolve_location()
    return {
        **service_card(),
        "default_location": loc.model_dump(),
        "locales": ["en", "hi", "bn"],
        "tabs": [
            "home",
            "analytics",
            "data",
            "map",
            "model",
            "chat",
            "settings",
            "overview",
            "nowcast",
            "alerts",
            "forecast",
            "predicted",
            "risks",
            "market",
            "advisor",
        ],
        "public_base_url": settings.public_base_url or None,
        "ollama": {
            "ok": ollama_ok,
            "detail": ollama_msg,
            "model": settings.ollama_model,
            "home": hub.status(),
        },
        "keys": {
            "imd_api_key": bool(settings.imd_api_key),
            "aikosh_api_key": bool(settings.aikosh_api_key),
            "data_gov_in_api_key": bool(settings.data_gov_in_api_key),
            "weatherbit_api_key": bool(settings.weatherbit_api_key),
        },
        "capabilities": capabilities(),
        "chat": {
            "sse": "POST {prefix}/chat with Accept: text/event-stream",
            "json": 'POST {prefix}/chat with {"stream": false} or Accept: application/json',
        },
    }

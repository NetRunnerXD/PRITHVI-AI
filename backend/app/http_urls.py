"""Absolute URLs for published API responses. No frontend assets."""

from __future__ import annotations

from fastapi import Request

from app.config import get_settings


def public_origin(request: Request | None = None) -> str:
    configured = (get_settings().public_base_url or "").strip().rstrip("/")
    if configured:
        return configured
    if request is not None:
        return str(request.base_url).rstrip("/")
    return "http://127.0.0.1:8000"


def api_url(path: str, request: Request | None = None) -> str:
    p = path if path.startswith("/") else f"/{path}"
    if not p.startswith("/api"):
        p = f"/api{p}"
    return f"{public_origin(request)}{p}"

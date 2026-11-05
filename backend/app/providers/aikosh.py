"""AIKosh client. Dataset list / metadata require AIKOSH_API_KEY.

Not on the request path: without a key it returns at once, and with a key the result is
cached for 6 h (one upstream call per query per 6 h, 1.5 s cap) so a slow or changed
AIKosh API never holds up a dashboard snapshot.
"""

from __future__ import annotations

import asyncio
from typing import Any

from app import cache
from app.config import get_settings
from app.providers.http import client

_TTL_S = 6 * 3600.0


async def _fetch(q: str) -> tuple[list[dict[str, Any]], str]:
    settings = get_settings()
    headers = {"Authorization": f"Bearer {settings.aikosh_api_key}"}
    try:
        r = await asyncio.wait_for(
            client().get(
                f"{settings.aikosh_api_base.rstrip('/')}/datasets",
                params={"q": q},
                headers=headers,
            ),
            1.5,
        )
        if r.status_code == 401:
            return [], "unauthorized"
        r.raise_for_status()
        data = r.json()
        if isinstance(data, list):
            return data, "ok"
        return data.get("results") or data.get("data") or [], "ok"
    except Exception:
        return [], "error"


async def search_datasets(q: str) -> tuple[list[dict[str, Any]], str]:
    settings = get_settings()
    if not settings.aikosh_api_key:
        return [], "missing_key"
    return await cache.aget(f"aikosh:{q}", lambda: _fetch(q), ttl_s=_TTL_S, swr_s=_TTL_S)

"""WAQI / AQICN geo feed. Optional token."""

from __future__ import annotations

from typing import Any

from app import cache
from app.config import get_settings
from app.providers.http import client

FEED = "https://api.waqi.info/feed/geo:{lat};{lon}/"


async def nearest(lat: float, lon: float) -> tuple[dict[str, Any] | None, str]:
    s = get_settings()
    token = getattr(s, "waqi_token", None)
    if not token:
        return None, "empty"
    key = f"waqi:{round(lat, 2)}:{round(lon, 2)}"
    hit = cache.get(key)
    if hit is not None:
        return hit, "ok" if hit else "empty"
    try:
        r = await client().get(FEED.format(lat=lat, lon=lon), params={"token": token}, timeout=8.0)
        if r.status_code >= 400:
            cache.set(key, None, 10 * 60)
            return None, "error"
        data = r.json() or {}
        if data.get("status") != "ok":
            cache.set(key, None, 10 * 60)
            return None, "empty"
        d = data.get("data") or {}
        iaqi = d.get("iaqi") or {}
        out = {
            "aqi": d.get("aqi"),
            "station": ((d.get("city") or {}).get("name")),
            "dominentpol": d.get("dominentpol"),
            "iaqi": {k: (v or {}).get("v") if isinstance(v, dict) else v for k, v in iaqi.items()},
            "source": "WAQI",
        }
        cache.set(key, out, 15 * 60)
        return out, "ok"
    except Exception:
        cache.set(key, None, 10 * 60)
        return None, "error"

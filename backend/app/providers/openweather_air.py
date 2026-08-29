"""OpenWeather air pollution API. Optional OPENWEATHER_API_KEY."""

from __future__ import annotations

from typing import Any

from app import cache
from app.config import get_settings
from app.providers.http import client

URL = "https://api.openweathermap.org/data/2.5/air_pollution"


async def current(lat: float, lon: float) -> tuple[dict[str, Any] | None, str]:
    s = get_settings()
    if not s.openweather_api_key:
        return None, "empty"
    key = f"owair:{round(lat, 2)}:{round(lon, 2)}"
    hit = cache.get(key)
    if hit is not None:
        return hit, "ok" if hit else "empty"
    try:
        r = await client().get(
            URL,
            params={"lat": lat, "lon": lon, "appid": s.openweather_api_key},
            timeout=8.0,
        )
        if r.status_code >= 400:
            cache.set(key, None, 10 * 60)
            return None, "error"
        lst = (r.json() or {}).get("list") or []
        if not lst:
            cache.set(key, None, 10 * 60)
            return None, "empty"
        row = lst[0]
        comps = row.get("components") or {}
        out = {
            "aqi": (row.get("main") or {}).get("aqi"),
            "components": comps,
            "source": "OpenWeatherMap Air Pollution",
        }
        cache.set(key, out, 15 * 60)
        return out, "ok"
    except Exception:
        cache.set(key, None, 10 * 60)
        return None, "error"

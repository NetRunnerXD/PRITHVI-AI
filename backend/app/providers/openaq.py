"""OpenAQ archive — historical PM near a point. Complements CPCB realtime NAQI."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from app import cache
from app.providers.http import client

V2 = "https://api.openaq.org/v2/measurements"


async def history(lat: float, lon: float, hours: int = 72) -> tuple[list[dict[str, Any]], str]:
    key = f"openaq:{round(lat, 2)}:{round(lon, 2)}"
    hit = cache.get(key)
    if hit is not None:
        return hit, "ok" if hit else "empty"
    since = (datetime.now(timezone.utc) - timedelta(hours=hours)).strftime("%Y-%m-%dT%H:%M:%SZ")
    params = {
        "coordinates": f"{lat},{lon}",
        "radius": 45000,
        "limit": 80,
        "parameter": ["pm25", "pm10", "no2", "so2", "o3", "co", "nh3", "bc"],
        "date_from": since,
        "order_by": "datetime",
        "sort": "asc",
    }
    try:
        r = await client().get(V2, params=params, timeout=8.0)
        if r.status_code >= 400:
            cache.set(key, [], 15 * 60)
            return [], "error"
        rows = (r.json() or {}).get("results") or []
        out = []
        for rec in rows:
            val = rec.get("value")
            dt = ((rec.get("date") or {}).get("utc")) or rec.get("date")
            if val is None or dt is None:
                continue
            out.append(
                {
                    "t": dt,
                    "value": float(val),
                    "unit": rec.get("unit") or "µg/m³",
                    "parameter": rec.get("parameter") or "pm25",
                    "location": rec.get("location"),
                    "source": "OpenAQ",
                }
            )
        cache.set(key, out, 20 * 60)
        return out, "ok" if out else "empty"
    except Exception:
        cache.set(key, [], 10 * 60)
        return [], "error"

"""Open-Meteo public thunder nowcast at hubs. No key. Not a lightning mapper."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from app import cache
from app.providers.http import client

URL = "https://api.open-meteo.com/v1/forecast"
IST = timezone(timedelta(hours=5, minutes=30))
PAST_H = 6


def _iso_local(s: str) -> datetime | None:
    try:
        t = datetime.fromisoformat(str(s).replace("Z", "+00:00"))
        if t.tzinfo is None:
            t = t.replace(tzinfo=IST)
        return t
    except ValueError:
        return None


async def fetch(lat: float, lon: float) -> dict[str, Any]:
    ck = f"om:th3:{round(lat, 2)}:{round(lon, 2)}"
    hit = cache.get(ck)
    if isinstance(hit, dict):
        return hit
    try:
        r = await client().get(
            URL,
            params={
                "latitude": lat,
                "longitude": lon,
                "current": "weather_code,precipitation,cloud_cover",
                "hourly": "cape,precipitation,weather_code",
                "forecast_hours": 3,
                "past_hours": PAST_H,
                "timezone": "Asia/Kolkata",
            },
        )
        r.raise_for_status()
        data = r.json()
        cur = data.get("current") or {}
        code = int(cur.get("weather_code") or 0)
        precip = float(cur.get("precipitation") or 0)
        hourly = data.get("hourly") or {}
        codes = hourly.get("weather_code") or []
        capes_h = hourly.get("cape") or []
        times = hourly.get("time") or []
        now = datetime.now(IST)
        hours: list[dict[str, Any]] = []
        capes_fwd: list[float] = []
        for i, hc_raw in enumerate(codes):
            hc = int(hc_raw or 0)
            h_cape = float(capes_h[i] or 0) if i < len(capes_h) and capes_h[i] is not None else 0.0
            ht = _iso_local(times[i]) if i < len(times) else None
            if ht is not None:
                lead_h = int(round((ht - now).total_seconds() / 3600.0))
            else:
                lead_h = i - PAST_H
            thunder = hc >= 95 or (hc >= 80 and h_cape >= 900)
            hours.append(
                {
                    "lead_h": lead_h,
                    "weather_code": hc,
                    "cape": h_cape,
                    "thunder": thunder,
                    "time": times[i] if i < len(times) else None,
                }
            )
            if lead_h >= 0:
                capes_fwd.append(h_cape)
        cape = max(capes_fwd) if capes_fwd else max((float(x) for x in capes_h[:3] if x is not None), default=0.0)
        thunder = code >= 95 or (code >= 80 and cape >= 900)
        if not any(h["lead_h"] == 0 for h in hours):
            hours.append({"lead_h": 0, "weather_code": code, "cape": cape, "thunder": thunder, "time": None})
        out = {
            "ok": True,
            "source": "open-meteo-thunder",
            "weather_code": code,
            "precip_mm": precip,
            "cape": cape,
            "thunder": thunder,
            "hours": hours,
            "status": "ok",
        }
        cache.set(ck, out, 180)
        return out
    except Exception:
        out = {"ok": False, "source": "open-meteo-thunder", "status": "error", "thunder": False, "hours": []}
        cache.set(ck, out, 90)
        return out


def agrees(kind: str, pack: dict[str, Any]) -> bool:
    code = int(pack.get("weather_code") or 0)
    precip = float(pack.get("precip_mm") or 0)
    if kind in {"lightning", "storm"}:
        return bool(pack.get("thunder")) or code >= 80 or precip > 0
    if kind in {"cloudburst", "downburst"}:
        return precip >= 0.2 or code >= 61
    return precip > 0 or code >= 51


def past_strikes(lat: float, lon: float, pack: dict[str, Any]) -> list[dict[str, Any]]:
    """Hub hours already in the past with thunder → observed past lightning (not GPS)."""
    out: list[dict[str, Any]] = []
    for row in pack.get("hours") or []:
        if int(row.get("lead_h") or 0) >= 0:
            continue
        if not row.get("thunder"):
            continue
        out.append(
            {
                "lat": lat,
                "lon": lon,
                "t": row.get("time"),
                "lead_h": row.get("lead_h"),
                "weather_code": row.get("weather_code"),
                "cape": row.get("cape"),
                "source": "open-meteo-thunder",
                "phase": "past",
                "kind": "lightning",
                "engine": "open-meteo-thunder",
            }
        )
    return out

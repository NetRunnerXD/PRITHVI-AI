from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from app import cache
from app.providers.http import client

URL = "https://power.larc.nasa.gov/api/temporal/daily/point"


_INFLIGHT_YEARS: set[str] = set()
_INFLIGHT_DAILY: set[str] = set()


async def _fetch_and_cache_years(key: str, lat: float, lon: float, years: int = 8) -> None:
    if key in _INFLIGHT_YEARS:
        return
    _INFLIGHT_YEARS.add(key)
    try:
        end = date.today() - timedelta(days=3)
        start = date(end.year - years, 1, 1)
        params = {
            "parameters": "PRECTOTCORR",
            "community": "AG",
            "longitude": lon,
            "latitude": lat,
            "start": start.strftime("%Y%m%d"),
            "end": end.strftime("%Y%m%d"),
            "format": "JSON",
        }
        r = await client().get(URL, params=params, timeout=25.0)
        if r.status_code == 200:
            data = r.json()
            cache.set(key, data, 24 * 60 * 60, swr_s=7 * 24 * 60 * 60)
    except Exception:
        pass
    finally:
        _INFLIGHT_YEARS.discard(key)


async def _fetch_and_cache_daily(key: str, lat: float, lon: float, days: int = 16) -> None:
    if key in _INFLIGHT_DAILY:
        return
    _INFLIGHT_DAILY.add(key)
    try:
        end = date.today() - timedelta(days=2)
        start = end - timedelta(days=days)
        params = {
            "parameters": "PRECTOTCORR,T2M,RH2M,ALLSKY_SFC_SW_DWN",
            "community": "AG",
            "longitude": lon,
            "latitude": lat,
            "start": start.strftime("%Y%m%d"),
            "end": end.strftime("%Y%m%d"),
            "format": "JSON",
        }
        r = await client().get(URL, params=params, timeout=10.0)
        if r.status_code == 200:
            data = r.json()
            cache.set(key, data, 12 * 60 * 60, swr_s=48 * 60 * 60)
    except Exception:
        pass
    finally:
        _INFLIGHT_DAILY.discard(key)


def seed_from_client(lat: float, lon: float, payload: dict[str, Any] | None, days: int = 16) -> bool:
    if not isinstance(payload, dict):
        return False
    key = f"nasa:{round(lat, 2)}:{round(lon, 2)}:{days}"
    cache.set(key, payload, 12 * 60 * 60, swr_s=48 * 60 * 60)
    return True


async def daily_point(lat: float, lon: float, days: int = 16) -> dict[str, Any]:
    key = f"nasa:{round(lat, 2)}:{round(lon, 2)}:{days}"
    hit = cache.get(key)
    if hit is not None and isinstance(hit, dict):
        return hit
    # Quick probe: if fast, return immediately; if slow, schedule background fetch so caller never blocks
    try:
        end = date.today() - timedelta(days=2)
        start = end - timedelta(days=days)
        params = {
            "parameters": "PRECTOTCORR,T2M,RH2M,ALLSKY_SFC_SW_DWN",
            "community": "AG",
            "longitude": lon,
            "latitude": lat,
            "start": start.strftime("%Y%m%d"),
            "end": end.strftime("%Y%m%d"),
            "format": "JSON",
        }
        r = await client().get(URL, params=params, timeout=1.0)
        if r.status_code == 200:
            data = r.json()
            cache.set(key, data, 12 * 60 * 60, swr_s=48 * 60 * 60)
            return data
    except Exception:
        pass
    import asyncio
    asyncio.create_task(_fetch_and_cache_daily(key, lat, lon, days))
    return {}


async def daily_years(lat: float, lon: float, years: int = 8) -> dict[str, Any]:
    """Multi-year daily PRECTOTCORR with non-blocking background hydration."""
    key = f"nasa:clim:{round(lat, 2)}:{round(lon, 2)}:{years}"
    hit = cache.get(key)
    if hit is not None and isinstance(hit, dict):
        return hit
    import asyncio
    asyncio.create_task(_fetch_and_cache_years(key, lat, lon, years))
    return {"properties": {"parameter": {"PRECTOTCORR": {}}}, "_loading": True}


def dated_precip(payload: dict[str, Any]) -> list[dict[str, Any]]:
    raw = payload.get("properties", {}).get("parameter", {}).get("PRECTOTCORR", {}) or {}
    rows = []
    for k, v in raw.items():
        try:
            fv = float(v)
        except (TypeError, ValueError):
            continue
        if fv <= -900:
            continue
        ks = str(k)
        date_s = f"{ks[:4]}-{ks[4:6]}-{ks[6:8]}" if len(ks) == 8 else ks
        rows.append({"date": date_s, "mm": round(fv, 2)})
    return rows


def precip_series(payload: dict[str, Any]) -> list[float]:
    raw = (
        payload.get("properties", {})
        .get("parameter", {})
        .get("PRECTOTCORR", {})
    )
    vals = []
    for v in raw.values():
        try:
            fv = float(v)
        except (TypeError, ValueError):
            continue
        if fv > -900:
            vals.append(fv)
    return vals

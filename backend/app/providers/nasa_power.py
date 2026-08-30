from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from app import cache
from app.providers.http import client

URL = "https://power.larc.nasa.gov/api/temporal/daily/point"


async def daily_point(lat: float, lon: float, days: int = 16) -> dict[str, Any]:
    key = f"nasa:{round(lat, 2)}:{round(lon, 2)}:{days}"
    hit = cache.get(key)
    if hit is not None:
        return hit
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
    r = await client().get(URL, params=params)
    r.raise_for_status()
    data = r.json()
    cache.set(key, data, 6 * 60 * 60)
    return data


async def daily_years(lat: float, lon: float, years: int = 8) -> dict[str, Any]:
    """Multi-year daily PRECTOTCORR for the historical module (free, no key)."""
    key = f"nasa:clim:{round(lat, 2)}:{round(lon, 2)}:{years}"
    hit = cache.get(key)
    if hit is not None:
        return hit
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
    r = await client().get(URL, params=params)
    r.raise_for_status()
    data = r.json()
    cache.set(key, data, 24 * 60 * 60)
    return data


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

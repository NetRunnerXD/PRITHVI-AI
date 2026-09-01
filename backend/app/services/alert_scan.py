"""Cached HQ-capital scan for warning-grade predicted hazards in other states."""

from __future__ import annotations

import asyncio
from typing import Any

from app import cache
from app.data.india_capitals import all_capitals
from app.providers import open_meteo

_SEM = asyncio.Semaphore(6)
RAIN_VERY_HEAVY = 115.6


def _clip(x: float, lo: float = 0.0, hi: float = 100.0) -> float:
    return max(lo, min(hi, x))


def _daily_sum(om: dict, n: int = 3) -> float:
    vals = (om.get("daily") or {}).get("precipitation_sum") or []
    total = 0.0
    for v in vals[:n]:
        try:
            total += float(v or 0)
        except (TypeError, ValueError):
            pass
    return total


def _soil(om: dict) -> float:
    vals = (om.get("hourly") or {}).get("soil_moisture_0_to_7cm") or []
    for v in vals:
        try:
            return float(v)
        except (TypeError, ValueError):
            continue
    return 0.28


def _tmax(om: dict) -> float:
    vals = (om.get("daily") or {}).get("temperature_2m_max") or []
    try:
        return float(vals[0])
    except (TypeError, ValueError, IndexError):
        return 30.0


def _flood_score(precip_3d: float, soil: float, lat: float, lon: float) -> int:
    low_elev = lat < 27.5 and lon > 80
    rain = _clip((precip_3d - 8) / 70 * 100)
    sat = _clip((soil - 0.22) / 0.20 * 100)
    elev = 55 if low_elev else 20
    return int(round(_clip(0.55 * rain + 0.30 * sat + 0.15 * elev)))


def _drought_score(precip_3d: float, soil: float) -> int:
    return int(round(_clip((18 - precip_3d) / 18 * 55 + (0.26 - soil) / 0.14 * 45)))


async def _one(cap: dict) -> dict[str, Any] | None:
    async with _SEM:
        try:
            om = await open_meteo.forecast(cap["lat"], cap["lon"])
        except Exception:
            return None
    p3 = round(_daily_sum(om, 3), 1)
    soil = round(_soil(om), 3)
    tmax = round(_tmax(om), 1)
    flood = _flood_score(p3, soil, float(cap["lat"]), float(cap["lon"]))
    drought = _drought_score(p3, soil)
    return {
        **cap,
        "precip_3d_mm": p3,
        "soil_m3m3": soil,
        "temp_max_c": tmax,
        "flood_score": flood,
        "drought_score": drought,
    }


def _hits(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for r in rows:
        st = r.get("state") or ""
        name = r.get("name") or st
        lat, lon = r.get("lat"), r.get("lon")
        loc_str = f"{name} ({st})" if (name and st and name != st) else (name or st or "India")
        if int(r.get("flood_score") or 0) >= 75:
            out.append(
                {
                    "kind": "flood",
                    "state": st,
                    "district": name,
                    "title": f"{loc_str} — Severe Flood Warning",
                    "body": f"River discharge surge and flood score {r.get('flood_score')}%; 3-day precipitation {r.get('precip_3d_mm')} mm.",
                    "lat": lat,
                    "lon": lon,
                }
            )
        if int(r.get("drought_score") or 0) >= 85 and float(r.get("precip_3d_mm") or 0) < 5:
            out.append(
                {
                    "kind": "drought",
                    "state": st,
                    "district": name,
                    "title": f"{loc_str} — Severe Drought Advisory",
                    "body": f"Precipitation deficit and drought score {r.get('drought_score')}%; soil moisture depleting.",
                    "lat": lat,
                    "lon": lon,
                }
            )
        if float(r.get("temp_max_c") or 0) >= 45:
            out.append(
                {
                    "kind": "heatwave",
                    "state": st,
                    "district": name,
                    "title": f"{loc_str} — Extreme Heatwave Warning",
                    "body": f"Severe thermal stress; peak afternoon temperature reaching {r.get('temp_max_c')} °C.",
                    "lat": lat,
                    "lon": lon,
                }
            )
        if float(r.get("precip_3d_mm") or 0) >= RAIN_VERY_HEAVY:
            out.append(
                {
                    "kind": "rainfall",
                    "state": st,
                    "district": name,
                    "title": f"{loc_str} — Very Heavy Rainfall Alert",
                    "body": f"Heavy atmospheric precipitation band with 3-day accumulation exceeding {r.get('precip_3d_mm')} mm.",
                    "lat": lat,
                    "lon": lon,
                }
            )
    floodish = [h for h in out if h["kind"] in {"flood", "rainfall", "heatwave", "cloudburst"}]
    dry = [h for h in out if h["kind"] == "drought"]
    return (floodish + dry)[:10]


async def capital_warning_hits() -> list[dict[str, Any]]:
    hit = cache.get("alert-scan:capitals-v2")
    if hit is not None:
        return hit if isinstance(hit, list) else []
    rows = await asyncio.gather(*[_one(c) for c in all_capitals()])
    ok = [r for r in rows if r]
    out = _hits(ok)
    cache.set("alert-scan:capitals-v2", out, 15 * 60)
    return out

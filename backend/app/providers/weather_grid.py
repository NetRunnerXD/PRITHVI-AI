"""Global Open-Meteo sample grid for Windy-style map layers.

Storm cells, lightning, and the forecast pin stay India-only.
"""

from __future__ import annotations

import math
import os
from datetime import datetime, timedelta, timezone
from typing import Any

from app import cache
from app.providers.http import client

FORECAST = "https://api.open-meteo.com/v1/forecast"
UTC = timezone.utc
SOUTH, WEST, NORTH, EAST = -56.0, -180.0, 72.0, 180.0
NY, NX = 13, 25
CHUNK = 20
HOURLY = (
    "temperature_2m,relative_humidity_2m,precipitation,precipitation_probability,"
    "pressure_msl,wind_speed_10m,wind_direction_10m,cloud_cover,cape,weather_code"
)
FIELDS = (
    "temp_c",
    "rh_pct",
    "precip_mm",
    "precip_prob_pct",
    "pressure_hpa",
    "wind_kmh",
    "wind_dir_deg",
    "wind_u",
    "wind_v",
    "cloud_pct",
    "cape",
)


def _lats() -> list[float]:
    if NY <= 1:
        return [round((SOUTH + NORTH) / 2, 3)]
    step = (NORTH - SOUTH) / (NY - 1)
    return [round(SOUTH + i * step, 3) for i in range(NY)]


def _lons() -> list[float]:
    if NX <= 1:
        return [round((WEST + EAST) / 2, 3)]
    step = (EAST - WEST) / (NX - 1)
    return [round(WEST + j * step, 3) for j in range(NX)]


def mesh() -> tuple[list[float], list[float], list[tuple[float, float]]]:
    lats, lons = _lats(), _lons()
    pts = [(la, lo) for la in lats for lo in lons]
    return lats, lons, pts


def _uv(speed_kmh: float | None, dir_deg: float | None) -> tuple[float | None, float | None]:
    if speed_kmh is None or dir_deg is None:
        return None, None
    ms = float(speed_kmh) / 3.6
    rad = math.radians(float(dir_deg))
    return round(-ms * math.sin(rad), 3), round(-ms * math.cos(rad), 3)


def _at(seq: list, i: int):
    if i < 0 or i >= len(seq):
        return None
    v = seq[i]
    if v is None:
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _hour_index(times: list[str], hour: int) -> int:
    hour = max(0, min(23, int(hour)))
    now = datetime.now(UTC).replace(minute=0, second=0, microsecond=0) + timedelta(hours=hour)
    want = now.strftime("%Y-%m-%dT%H:00")
    for i, t in enumerate(times):
        if str(t)[:16] == want:
            return i
    if not times:
        return 0
    return min(hour, len(times) - 1)


def synthetic(hour: int = 0) -> dict[str, Any]:
    """Deterministic grid for tests / when Open-Meteo is unreachable."""
    lats, lons, pts = mesh()
    fields: dict[str, list] = {k: [] for k in FIELDS}
    for la, lo in pts:
        t = 26.0 * math.cos(math.radians(la * 0.92)) - 2.0 + hour * 0.12 + 2.0 * math.sin(math.radians(lo))
        rh = max(18.0, min(97.0, 58 + 28 * math.cos(math.radians(la)) - t * 0.4))
        p = max(0.0, 3.5 * max(0.0, math.cos(math.radians(la * 1.2))) + (hour % 8) * 0.15)
        wind = 7.0 + abs(la) * 0.18 + 4.0 * abs(math.sin(math.radians(lo)))
        wdir = (270.0 + lo * 0.4 + la * 0.2) % 360
        u, v = _uv(wind, wdir)
        fields["temp_c"].append(round(t, 2))
        fields["rh_pct"].append(round(rh, 0))
        fields["precip_mm"].append(round(p, 2))
        fields["precip_prob_pct"].append(int(min(90, p * 12)))
        fields["pressure_hpa"].append(round(1008 - (la - 22) * 0.4, 1))
        fields["wind_kmh"].append(round(wind, 1))
        fields["wind_dir_deg"].append(round(wdir, 0))
        fields["wind_u"].append(u)
        fields["wind_v"].append(v)
        fields["cloud_pct"].append(int(min(100, 30 + p * 12)))
        fields["cape"].append(int(max(0, (t - 26) * 180)))
    return {
        "ok": True,
        "source": "synthetic",
        "note": "Global model field (not radar). Storms and the forecast pin stay India-only. Hours are UTC.",
        "scope": "world",
        "south": SOUTH,
        "west": WEST,
        "north": NORTH,
        "east": EAST,
        "nx": NX,
        "ny": NY,
        "lats": lats,
        "lons": lons,
        "hour": hour,
        "n": len(pts),
        "fields": fields,
        "products": [
            "wind",
            "temp",
            "precip",
            "pressure",
            "clouds",
            "humidity",
            "cape",
            "radar",
            "satellite",
        ],
    }


async def _fetch_chunk(pts: list[tuple[float, float]]) -> list[dict[str, Any]]:
    lat = ",".join(str(p[0]) for p in pts)
    lon = ",".join(str(p[1]) for p in pts)
    r = await client().get(
        FORECAST,
        params={
            "latitude": lat,
            "longitude": lon,
            "hourly": HOURLY,
            "forecast_hours": 24,
            "timezone": "GMT",
            "wind_speed_unit": "kmh",
        },
    )
    r.raise_for_status()
    body = r.json()
    if isinstance(body, list):
        return body
    return [body]


async def fetch_raw() -> list[dict[str, Any]] | None:
    key = "om:world-grid:raw:v2"
    hit = cache.get(key)
    if isinstance(hit, list) and hit:
        return hit
    if os.environ.get("PYTEST_CURRENT_TEST"):
        return None
    _, _, pts = mesh()
    rows: list[dict[str, Any]] = []
    try:
        for i in range(0, len(pts), CHUNK):
            rows.extend(await _fetch_chunk(pts[i : i + CHUNK]))
    except Exception:
        return None
    if len(rows) != len(pts):
        return None
    cache.set(key, rows, 8 * 60)
    return rows


def _slice(rows: list[dict[str, Any]], hour: int) -> dict[str, Any]:
    lats, lons, pts = mesh()
    fields: dict[str, list] = {k: [] for k in FIELDS}
    times = (rows[0].get("hourly") or {}).get("time") or []
    idx = _hour_index([str(x) for x in times], hour)
    stamp = str(times[idx]) if idx < len(times) else None
    for row in rows:
        h = row.get("hourly") or {}
        temp = _at(h.get("temperature_2m") or [], idx)
        rh = _at(h.get("relative_humidity_2m") or [], idx)
        precip = _at(h.get("precipitation") or [], idx)
        prob = _at(h.get("precipitation_probability") or [], idx)
        pres = _at(h.get("pressure_msl") or [], idx)
        wspd = _at(h.get("wind_speed_10m") or [], idx)
        wdir = _at(h.get("wind_direction_10m") or [], idx)
        cloud = _at(h.get("cloud_cover") or [], idx)
        cape = _at(h.get("cape") or [], idx)
        u, v = _uv(wspd, wdir)
        fields["temp_c"].append(None if temp is None else round(temp, 2))
        fields["rh_pct"].append(None if rh is None else round(rh, 0))
        fields["precip_mm"].append(None if precip is None else round(precip, 2))
        fields["precip_prob_pct"].append(None if prob is None else int(prob))
        fields["pressure_hpa"].append(None if pres is None else round(pres, 1))
        fields["wind_kmh"].append(None if wspd is None else round(wspd, 1))
        fields["wind_dir_deg"].append(None if wdir is None else round(wdir, 0))
        fields["wind_u"].append(u)
        fields["wind_v"].append(v)
        fields["cloud_pct"].append(None if cloud is None else round(cloud, 0))
        fields["cape"].append(None if cape is None else round(cape, 0))
    return {
        "ok": True,
        "source": "open-meteo",
        "note": "Global Open-Meteo field (not a rain-gauge). Storm cells and the forecast pin stay India-only. Hours are UTC.",
        "scope": "world",
        "south": SOUTH,
        "west": WEST,
        "north": NORTH,
        "east": EAST,
        "nx": NX,
        "ny": NY,
        "lats": lats,
        "lons": lons,
        "hour": hour,
        "valid": stamp,
        "n": len(pts),
        "fields": fields,
        "products": [
            "wind",
            "temp",
            "precip",
            "pressure",
            "clouds",
            "humidity",
            "cape",
            "radar",
            "satellite",
        ],
    }


async def world_grid(hour: int = 0) -> dict[str, Any]:
    hour = max(0, min(23, int(hour)))
    key = f"om:world-grid:h{hour}:v2"
    hit = cache.get(key)
    if isinstance(hit, dict) and hit.get("fields"):
        return hit
    raw = await fetch_raw()
    pack = _slice(raw, hour) if raw else synthetic(hour)
    if pack.get("source") == "synthetic" and not os.environ.get("PYTEST_CURRENT_TEST"):
        pack["ok"] = False
        pack["note"] = "Open-Meteo grid unavailable; showing a labelled placeholder."
    cache.set(key, pack, 8 * 60)
    return pack


async def india_grid(hour: int = 0) -> dict[str, Any]:
    return await world_grid(hour)

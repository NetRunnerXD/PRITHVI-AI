from __future__ import annotations

import json
from typing import Any

from app import cache
from app.config import ROOT
from app.providers.http import client

FORECAST = "https://api.open-meteo.com/v1/forecast"
_GOOD = ROOT / ".cache" / "om_last"
FLOOD = "https://flood-api.open-meteo.com/v1/flood"
AIR = "https://air-quality-api.open-meteo.com/v1/air-quality"
MARINE = "https://marine-api.open-meteo.com/v1/marine"
ARCHIVE = "https://archive-api.open-meteo.com/v1/archive"
GEO = "https://geocoding-api.open-meteo.com/v1/search"


def _good_path(kind: str, lat: float, lon: float):
    return _GOOD / f"{kind}_{round(lat, 2)}_{round(lon, 2)}.json"


def _save_good(kind: str, lat: float, lon: float, data: dict[str, Any]) -> None:
    try:
        _GOOD.mkdir(parents=True, exist_ok=True)
        slim = {k: v for k, v in data.items() if not str(k).startswith("_")}
        _good_path(kind, lat, lon).write_text(json.dumps(slim), encoding="utf-8")
    except OSError:
        pass


def _load_good(kind: str, lat: float, lon: float) -> dict[str, Any] | None:
    p = _good_path(kind, lat, lon)
    if not p.exists():
        return None
    try:
        blob = json.loads(p.read_text(encoding="utf-8"))
        return blob if isinstance(blob, dict) and (blob.get("current") or blob.get("hourly") or blob.get("daily")) else None
    except (OSError, json.JSONDecodeError):
        return None


async def forecast(lat: float, lon: float) -> dict[str, Any]:
    key = f"om:fc3:{round(lat, 3)}:{round(lon, 3)}"
    hit = cache.get(key)
    if isinstance(hit, dict) and (hit.get("current") or hit.get("hourly")):
        return hit
    params = {
        "latitude": lat,
        "longitude": lon,
        "current": "temperature_2m,relative_humidity_2m,precipitation,weather_code,wind_speed_10m,wind_direction_10m,cloud_cover,is_day,visibility",
        "hourly": (
            "temperature_2m,precipitation_probability,precipitation,soil_moisture_0_to_7cm,"
            "et0_fao_evapotranspiration,relative_humidity_2m,dew_point_2m,pressure_msl,"
            "wind_speed_10m,wind_direction_10m,wind_gusts_10m,cloud_cover,cloud_cover_low,"
            "cloud_cover_mid,cloud_cover_high,weather_code,visibility,cape,vapour_pressure_deficit"
        ),
        "past_days": 1,
        "daily": "precipitation_sum,precipitation_probability_max,temperature_2m_max,temperature_2m_min,et0_fao_evapotranspiration,weather_code,wind_speed_10m_max,wind_direction_10m_dominant",
        "forecast_days": 7,
        "timezone": "Asia/Kolkata",
    }
    try:
        r = await client().get(FORECAST, params=params)
        if r.status_code == 429:
            good = _load_good("fc", lat, lon) or await _archive_fallback(lat, lon)
            if good:
                good["_stale"] = True
                good["_stale_reason"] = "open-meteo-429"
                cache.set(key, good, 180)
                return good
            r.raise_for_status()
        r.raise_for_status()
        data = r.json()
        if isinstance(data, dict) and not data.get("error"):
            _save_good("fc", lat, lon, data)
            cache.set(key, data, 300)
            return data
        good = _load_good("fc", lat, lon)
        if good:
            good["_stale"] = True
            return good
        return data if isinstance(data, dict) else {}
    except Exception:
        good = _load_good("fc", lat, lon) or await _archive_fallback(lat, lon)
        if good:
            good["_stale"] = True
            good["_stale_reason"] = "open-meteo-error"
            cache.set(key, good, 180)
            return good
        raise


async def _archive_fallback(lat: float, lon: float) -> dict[str, Any] | None:
    """ERA5 archive when the live forecast quota is gone. Not a gauge."""
    from datetime import date, timedelta

    today = date.today()
    try:
        r = await client().get(
            ARCHIVE,
            params={
                "latitude": lat,
                "longitude": lon,
                "start_date": (today - timedelta(days=1)).isoformat(),
                "end_date": today.isoformat(),
                "hourly": (
                    "temperature_2m,precipitation,relative_humidity_2m,weather_code,"
                    "wind_speed_10m,wind_direction_10m,cloud_cover,et0_fao_evapotranspiration,"
                    "soil_moisture_0_to_7cm"
                ),
                "daily": "precipitation_sum,temperature_2m_max,temperature_2m_min,et0_fao_evapotranspiration,weather_code",
                "timezone": "Asia/Kolkata",
            },
        )
        if r.status_code >= 400:
            return None
        data = r.json()
        hourly = data.get("hourly") or {}
        temps = hourly.get("temperature_2m") or []
        last = None
        for i in range(len(temps) - 1, -1, -1):
            if temps[i] is not None:
                last = i
                break
        if last is None:
            return None

        def _h(name: str):
            row = hourly.get(name) or []
            return row[last] if last < len(row) else None

        data["current"] = {
            "temperature_2m": _h("temperature_2m"),
            "relative_humidity_2m": _h("relative_humidity_2m"),
            "precipitation": _h("precipitation"),
            "weather_code": _h("weather_code"),
            "wind_speed_10m": _h("wind_speed_10m"),
            "wind_direction_10m": _h("wind_direction_10m"),
            "cloud_cover": _h("cloud_cover"),
            "is_day": 1,
            "time": (hourly.get("time") or [None])[last],
        }
        data["_archive_fallback"] = True
        _save_good("fc", lat, lon, data)
        return data
    except Exception:
        return None


async def flood(lat: float, lon: float) -> dict[str, Any]:
    key = f"om:fl:{round(lat, 3)}:{round(lon, 3)}"
    hit = cache.get(key)
    if hit is not None:
        return hit
    params = {
        "latitude": lat,
        "longitude": lon,
        "daily": "river_discharge,river_discharge_mean,river_discharge_max",
        "forecast_days": 7,
    }
    r = await client().get(FLOOD, params=params)
    r.raise_for_status()
    data = r.json()
    cache.set(key, data, 60 * 60)
    return data


async def air_quality(lat: float, lon: float) -> dict[str, Any]:
    key = f"om:aq:{round(lat, 3)}:{round(lon, 3)}"
    hit = cache.get(key)
    if hit is not None:
        return hit
    params = {
        "latitude": lat,
        "longitude": lon,
        "current": "pm10,pm2_5,carbon_monoxide,ozone,nitrogen_dioxide,us_aqi,european_aqi",
        "hourly": "pm10,pm2_5,us_aqi,european_aqi",
        "forecast_days": 3,
        "past_days": 7,
        "timezone": "Asia/Kolkata",
    }
    r = await client().get(AIR, params=params)
    r.raise_for_status()
    data = r.json()
    cache.set(key, data, 5 * 60)
    return data


async def marine(lat: float, lon: float) -> dict[str, Any]:
    key = f"om:mr:{round(lat, 3)}:{round(lon, 3)}"
    hit = cache.get(key)
    if hit is not None:
        return hit
    params = {
        "latitude": lat,
        "longitude": lon,
        "current": "wave_height,wave_direction,wave_period,wind_wave_height",
        "hourly": "wave_height,wave_direction,wave_period",
        "forecast_days": 3,
        "timezone": "Asia/Kolkata",
    }
    r = await client().get(MARINE, params=params)
    if r.status_code >= 400:
        data = {"inland": True, "reason": "no marine grid cell at this point"}
        cache.set(key, data, 60 * 60)
        return data
    data = r.json()
    cur = data.get("current") or {}
    if cur.get("wave_height") is None and not any((data.get("hourly") or {}).get("wave_height") or []):
        data["inland"] = True
    cache.set(key, data, 3 * 60)
    return data


async def daily_window(lat: float, lon: float, start: str, end: str) -> dict[str, Any]:
    """Daily precip/temps for [start, end] (YYYY-MM-DD). Forecast and/or archive."""
    from datetime import date, timedelta

    from app.science.nowcast import _now

    key = f"om:win:{round(lat, 3)}:{round(lon, 3)}:{start}:{end}"
    hit = cache.get(key)
    if hit is not None:
        return hit
    today = _now().date()
    start_d = date.fromisoformat(start)
    end_d = date.fromisoformat(end)
    if end_d < start_d:
        start_d, end_d = end_d, start_d
    horizon = today + timedelta(days=16)
    daily_keys = "precipitation_sum,precipitation_probability_max,temperature_2m_max,temperature_2m_min,weather_code"
    merged: dict[str, list] = {
        "time": [],
        "precipitation_sum": [],
        "precipitation_probability_max": [],
        "temperature_2m_max": [],
        "temperature_2m_min": [],
        "weather_code": [],
    }

    async def _pull(url: str, a: date, b: date) -> None:
        if b < a:
            return
        params = {
            "latitude": lat,
            "longitude": lon,
            "daily": daily_keys,
            "start_date": a.isoformat(),
            "end_date": b.isoformat(),
            "timezone": "Asia/Kolkata",
        }
        r = await client().get(url, params=params)
        r.raise_for_status()
        block = (r.json().get("daily") or {})
        times = list(block.get("time") or [])
        for i, t in enumerate(times):
            if t in merged["time"]:
                continue
            merged["time"].append(t)
            for k in merged:
                if k == "time":
                    continue
                vals = block.get(k) or []
                merged[k].append(vals[i] if i < len(vals) else None)

    past_end = min(end_d, today - timedelta(days=1))
    if past_end >= start_d:
        await _pull(ARCHIVE, start_d, past_end)
    fut_start = max(start_d, today)
    fut_end = min(end_d, horizon)
    if fut_end >= fut_start:
        await _pull(FORECAST, fut_start, fut_end)
    out = {
        "daily": merged,
        "start": start_d.isoformat(),
        "end": end_d.isoformat(),
        "horizon": horizon.isoformat(),
        "clipped_end": min(end_d, horizon).isoformat(),
    }
    cache.set(key, out, 180)
    return out


async def geocode_india(name: str) -> list[dict[str, Any]]:
    params = {"name": name, "count": 8, "language": "en", "countryCode": "IN"}
    r = await client().get(GEO, params=params)
    r.raise_for_status()
    return r.json().get("results") or []

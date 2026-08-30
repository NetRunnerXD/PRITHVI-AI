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


_FC_CURRENT = (
    "temperature_2m,relative_humidity_2m,apparent_temperature,dew_point_2m,"
    "precipitation,rain,showers,snowfall,weather_code,wind_speed_10m,wind_direction_10m,"
    "wind_gusts_10m,cloud_cover,is_day,visibility,pressure_msl,surface_pressure"
)
_FC_HOURLY = (
    "temperature_2m,precipitation_probability,precipitation,rain,showers,snowfall,snow_depth,"
    "soil_moisture_0_to_7cm,et0_fao_evapotranspiration,evapotranspiration,relative_humidity_2m,"
    "dew_point_2m,apparent_temperature,pressure_msl,surface_pressure,"
    "wind_speed_10m,wind_direction_10m,wind_gusts_10m,cloud_cover,cloud_cover_low,"
    "cloud_cover_mid,cloud_cover_high,weather_code,visibility,cape,vapour_pressure_deficit"
)
_FC_HOURLY_EXTRA = (
    "temperature_80m,temperature_120m,temperature_180m,"
    "wind_speed_80m,wind_speed_120m,wind_speed_180m,"
    "wind_direction_80m,wind_direction_120m,wind_direction_180m,"
    "soil_temperature_0cm,soil_temperature_6cm,soil_temperature_18cm,soil_temperature_54cm,"
    "soil_moisture_0_to_1cm,soil_moisture_1_to_3cm,soil_moisture_3_to_9cm,"
    "soil_moisture_9_to_27cm,soil_moisture_27_to_81cm"
)
_FC_DAILY = (
    "precipitation_sum,precipitation_probability_max,precipitation_hours,"
    "rain_sum,showers_sum,snowfall_sum,"
    "temperature_2m_max,temperature_2m_min,temperature_2m_mean,"
    "apparent_temperature_max,apparent_temperature_min,"
    "relative_humidity_2m_max,relative_humidity_2m_min,relative_humidity_2m_mean,"
    "dew_point_2m_max,dew_point_2m_min,dew_point_2m_mean,"
    "et0_fao_evapotranspiration,weather_code,"
    "wind_speed_10m_max,wind_speed_10m_mean,wind_gusts_10m_max,wind_direction_10m_dominant,"
    "sunrise,sunset,daylight_duration,sunshine_duration,shortwave_radiation_sum,"
    "uv_index_max,uv_index_clear_sky_max"
)


def _merge_om(base: dict[str, Any], extra: dict[str, Any]) -> dict[str, Any]:
    out = dict(base)
    for block in ("hourly", "daily", "current"):
        a = dict(out.get(block) or {})
        b = extra.get(block) or {}
        if isinstance(b, dict):
            a.update({k: v for k, v in b.items() if k not in a or a.get(k) in (None, [])})
            out[block] = a
    return out


async def forecast(lat: float, lon: float) -> dict[str, Any]:
    key = f"om:fc4:{round(lat, 3)}:{round(lon, 3)}"

    async def factory() -> dict[str, Any]:
        params = {
            "latitude": lat,
            "longitude": lon,
            "current": _FC_CURRENT,
            "hourly": _FC_HOURLY,
            "past_days": 1,
            "daily": _FC_DAILY,
            "forecast_days": 7,
            "timezone": "Asia/Kolkata",
        }
        extra_params = {
            "latitude": lat,
            "longitude": lon,
            "hourly": _FC_HOURLY_EXTRA,
            "past_days": 1,
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
                    return good
                r.raise_for_status()
            r.raise_for_status()
            data = r.json()
            if isinstance(data, dict) and not data.get("error"):
                try:
                    r2 = await client().get(FORECAST, params=extra_params)
                    if r2.status_code < 400:
                        extra = r2.json()
                        if isinstance(extra, dict) and not extra.get("error"):
                            data = _merge_om(data, extra)
                except Exception:
                    pass
                _save_good("fc", lat, lon, data)
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
                return good
            raise

    return await cache.aget(key, factory, ttl_s=90, swr_s=600)


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


def _flood_has_discharge(data: dict[str, Any]) -> bool:
    disc = ((data or {}).get("daily") or {}).get("river_discharge") or []
    return any(x is not None for x in disc)


async def flood(lat: float, lon: float) -> dict[str, Any]:
    key = f"om:fl2:{round(lat, 3)}:{round(lon, 3)}"

    async def _pull(a: float, b: float) -> dict[str, Any]:
        r = await client().get(
            FLOOD,
            params={
                "latitude": a,
                "longitude": b,
                "daily": "river_discharge,river_discharge_mean,river_discharge_max",
                "forecast_days": 7,
            },
        )
        r.raise_for_status()
        return r.json()

    async def factory() -> dict[str, Any]:
        data = await _pull(lat, lon)
        if _flood_has_discharge(data):
            return data
        for dlat, dlon in ((0.6, -0.4), (0.8, 0.0), (-0.5, 0.3), (1.1, -0.7), (0.0, -0.8)):
            try:
                alt = await _pull(lat + dlat, lon + dlon)
            except Exception:
                continue
            if _flood_has_discharge(alt):
                alt["_snapped"] = True
                alt["_snap_lat"] = lat + dlat
                alt["_snap_lon"] = lon + dlon
                return alt
        return data

    return await cache.aget(key, factory, ttl_s=60 * 60, swr_s=3 * 3600)


async def air_quality(lat: float, lon: float) -> dict[str, Any]:
    key = f"om:aq2:{round(lat, 3)}:{round(lon, 3)}"

    async def factory() -> dict[str, Any]:
        aq_vars = (
            "pm10,pm2_5,carbon_monoxide,carbon_dioxide,nitrogen_dioxide,sulphur_dioxide,"
            "ozone,ammonia,methane,dust,uv_index,uv_index_clear_sky,"
            "alder_pollen,birch_pollen,grass_pollen,mugwort_pollen,olive_pollen,ragweed_pollen,"
            "us_aqi,european_aqi"
        )
        params = {
            "latitude": lat,
            "longitude": lon,
            "current": aq_vars,
            "hourly": aq_vars,
            "forecast_days": 3,
            "past_days": 7,
            "timezone": "Asia/Kolkata",
        }
        r = await client().get(AIR, params=params)
        r.raise_for_status()
        return r.json()

    return await cache.aget(key, factory, ttl_s=5 * 60, swr_s=20 * 60)


async def marine(lat: float, lon: float) -> dict[str, Any]:
    key = f"om:mr2:{round(lat, 3)}:{round(lon, 3)}"

    async def factory() -> dict[str, Any]:
        marine_vars = (
            "wave_height,wave_direction,wave_period,wave_peak_period,"
            "wind_wave_height,wind_wave_direction,wind_wave_period,wind_wave_peak_period,"
            "swell_wave_height,swell_wave_direction,swell_wave_period,swell_wave_peak_period,"
            "secondary_swell_wave_height,secondary_swell_wave_direction,secondary_swell_wave_period,"
            "tertiary_swell_wave_height,tertiary_swell_wave_direction,tertiary_swell_wave_period,"
            "sea_level_height_msl,sea_surface_temperature,"
            "ocean_current_velocity,ocean_current_direction"
        )
        params = {
            "latitude": lat,
            "longitude": lon,
            "current": marine_vars,
            "hourly": marine_vars,
            "forecast_days": 3,
            "timezone": "Asia/Kolkata",
        }
        r = await client().get(MARINE, params=params)
        if r.status_code >= 400:
            return {"inland": True, "reason": "no marine grid cell at this point"}
        data = r.json()
        cur = data.get("current") or {}
        if cur.get("wave_height") is None and not any((data.get("hourly") or {}).get("wave_height") or []):
            data["inland"] = True
        return data

    return await cache.aget(key, factory, ttl_s=3 * 60, swr_s=15 * 60)


def _slice_forecast_daily(lat: float, lon: float, start: str, end: str) -> dict[str, Any] | None:
    """Reuse a warm Open-Meteo forecast pack instead of a second HTTP call."""
    fc = cache.get(f"om:fc4:{round(lat, 3)}:{round(lon, 3)}") or cache.peek(f"om:fc4:{round(lat, 3)}:{round(lon, 3)}")
    if not isinstance(fc, dict):
        return None
    daily = fc.get("daily") or {}
    times = [str(t)[:10] for t in (daily.get("time") or [])]
    if not times:
        return None
    have = set(times)
    from datetime import date, timedelta

    start_d = date.fromisoformat(start)
    end_d = date.fromisoformat(end)
    if end_d < start_d:
        start_d, end_d = end_d, start_d
    wanted: list[str] = []
    cur = start_d
    while cur <= end_d:
        wanted.append(cur.isoformat())
        cur += timedelta(days=1)
    if any(d not in have for d in wanted):
        return None
    keys = (
        "precipitation_sum",
        "precipitation_probability_max",
        "temperature_2m_max",
        "temperature_2m_min",
        "weather_code",
        "wind_speed_10m_max",
        "wind_speed_10m_mean",
        "wind_gusts_10m_max",
        "wind_direction_10m_dominant",
    )
    merged: dict[str, list] = {k: [] for k in ("time",) + keys}
    for i, t in enumerate(times):
        if t < start_d.isoformat() or t > end_d.isoformat():
            continue
        merged["time"].append(t)
        for k in keys:
            vals = daily.get(k) or []
            merged[k].append(vals[i] if i < len(vals) else None)
    today = times[-1]
    return {
        "daily": merged,
        "start": start_d.isoformat(),
        "end": end_d.isoformat(),
        "horizon": today,
        "clipped_end": end_d.isoformat(),
        "from_forecast_cache": True,
    }


async def daily_window(lat: float, lon: float, start: str, end: str) -> dict[str, Any]:
    """Daily precip/temps for [start, end] (YYYY-MM-DD). Forecast and/or archive."""
    from datetime import date, timedelta

    from app.science.nowcast import _now

    key = f"om:win:{round(lat, 3)}:{round(lon, 3)}:{start}:{end}"

    async def factory() -> dict[str, Any]:
        sliced = _slice_forecast_daily(lat, lon, start, end)
        if sliced:
            return sliced
        today = _now().date()
        start_d = date.fromisoformat(start)
        end_d = date.fromisoformat(end)
        if end_d < start_d:
            start_d, end_d = end_d, start_d
        horizon = today + timedelta(days=16)
        daily_keys = (
            "precipitation_sum,precipitation_probability_max,temperature_2m_max,temperature_2m_min,"
            "weather_code,wind_speed_10m_max,wind_speed_10m_mean,wind_gusts_10m_max,wind_direction_10m_dominant"
        )
        merged: dict[str, list] = {
            "time": [],
            "precipitation_sum": [],
            "precipitation_probability_max": [],
            "temperature_2m_max": [],
            "temperature_2m_min": [],
            "weather_code": [],
            "wind_speed_10m_max": [],
            "wind_speed_10m_mean": [],
            "wind_gusts_10m_max": [],
            "wind_direction_10m_dominant": [],
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
        return {
            "daily": merged,
            "start": start_d.isoformat(),
            "end": end_d.isoformat(),
            "horizon": horizon.isoformat(),
            "clipped_end": min(end_d, horizon).isoformat(),
        }

    return await cache.aget(key, factory, ttl_s=180, swr_s=900)


async def geocode_india(name: str) -> list[dict[str, Any]]:
    from app.data.fuzzy import fold

    key = f"om:geo:{fold(name or '')}"

    async def factory() -> list[dict[str, Any]]:
        params = {"name": name, "count": 8, "language": "en", "countryCode": "IN"}
        r = await client().get(GEO, params=params)
        r.raise_for_status()
        return r.json().get("results") or []

    return await cache.aget(key, factory, ttl_s=24 * 3600, swr_s=7 * 86400)

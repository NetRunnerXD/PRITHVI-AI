from __future__ import annotations

from datetime import datetime, timedelta, timezone
from statistics import mean, pstdev
from typing import Any

IST = timezone(timedelta(hours=5, minutes=30))


def _today_ist() -> str:
    return datetime.now(IST).date().isoformat()


def _start_today(times: list) -> int:
    """Index of calendar today (IST) in an Open-Meteo daily time list.

    past_days=1 puts yesterday first. Non-ISO fixtures stay at 0.
    """
    today = _today_ist()
    for i, t in enumerate(times):
        s = str(t)[:10]
        if len(s) >= 10 and s[4:5] == "-" and s >= today:
            return i
    return 0


def _daily(om: dict, key: str) -> list[float]:
    vals = (om.get("daily") or {}).get(key) or []
    out = []
    for v in vals:
        try:
            out.append(float(v) if v is not None else 0.0)
        except (TypeError, ValueError):
            out.append(0.0)
    return out


def _hourly(om: dict, key: str) -> list[float]:
    vals = (om.get("hourly") or {}).get(key) or []
    out = []
    for v in vals:
        try:
            if v is None:
                continue
            out.append(float(v))
        except (TypeError, ValueError):
            continue
    return out


def extract(
    om: dict,
    flood: dict,
    nasa_precip: list[float],
    aqi: dict | None = None,
    marine: dict | None = None,
) -> dict[str, Any]:
    daily_times_all = list((om.get("daily") or {}).get("time") or [])
    start = _start_today(daily_times_all)
    precip_all = _daily(om, "precipitation_sum")
    precip = precip_all[start:]
    probs = _daily(om, "precipitation_probability_max")[start:]
    tmax = _daily(om, "temperature_2m_max")[start:]
    tmin = _daily(om, "temperature_2m_min")[start:]
    et0 = _daily(om, "et0_fao_evapotranspiration")[start:]
    daily_wind_max = _daily(om, "wind_speed_10m_max")[start:]
    daily_wind_dir = _daily(om, "wind_direction_10m_dominant")[start:]
    daily_times = daily_times_all[start:]
    precip_yesterday = float(precip_all[start - 1]) if start > 0 and start - 1 < len(precip_all) else None
    soil = _hourly(om, "soil_moisture_0_to_7cm")
    current = om.get("current") or {}
    marine = marine or {}
    mcur = marine.get("current") or {}
    aq = aqi or {}
    aq_cur = aq.get("current") or {}

    precip_3d = sum(precip[:3])
    precip_today = precip[0] if precip else 0.0
    soil_now = soil[0] if soil else None
    if soil_now is None:
        soil_now = soil[-1] if soil else 0.30

    discharge = (flood.get("daily") or {}).get("river_discharge") or []
    dvals = [float(x) for x in discharge if x is not None]
    dmean = (flood.get("daily") or {}).get("river_discharge_mean") or []
    dmean_vals = [float(x) for x in dmean if x is not None]

    if len(dvals) >= 2:
        trend = "rising" if dvals[1] > dvals[0] * 1.08 else "falling" if dvals[1] < dvals[0] * 0.92 else "steady"
    else:
        trend = "steady"

    clim_daily = mean(nasa_precip) if nasa_precip else 6.0
    clim_3d = clim_daily * 3
    ratio = precip_3d / clim_3d if clim_3d > 0 else 1.0
    if len(nasa_precip) >= 5:
        sd = pstdev(nasa_precip) or 1.0
        z = (precip_today - clim_daily) / sd
    else:
        z = (ratio - 1.0) * 1.5

    us_aqi = aq_cur.get("us_aqi")
    wave_vals = _hourly(marine, "wave_height")[:72]
    inland = bool(marine.get("inland")) or (mcur.get("wave_height") is None and not wave_vals)

    return {
        "precip_today_mm": precip_today,
        "precip_yesterday_mm": precip_yesterday,
        "precip_3d_mm": precip_3d,
        "precip_7d_mm": sum(precip[:7]),
        "precip_days": precip,
        "precip_prob": [int(p) for p in probs],
        "temp_max": tmax,
        "temp_min": tmin,
        "et0_days": et0,
        "et0_today": et0[0] if et0 else 0.0,
        "soil_m3m3": float(soil_now),
        "temp_now": current.get("temperature_2m"),
        "rh_now": current.get("relative_humidity_2m"),
        "wind_now": current.get("wind_speed_10m"),
        "wind_dir_now": current.get("wind_direction_10m"),
        "cloud_now": current.get("cloud_cover"),
        "is_day": current.get("is_day"),
        "visibility_m": current.get("visibility"),
        "precip_now": current.get("precipitation"),
        "weather_code": current.get("weather_code"),
        "discharge": dvals,
        "discharge_mean": dmean_vals,
        "discharge_trend": trend,
        "clim_daily_mm": clim_daily,
        "clim_3d_mm": clim_3d,
        "precip_ratio": ratio,
        "precip_z": z,
        "us_aqi": us_aqi,
        "eu_aqi": aq_cur.get("european_aqi"),
        "om_pm25": aq_cur.get("pm2_5"),
        "om_pm10": aq_cur.get("pm10"),
        "om_no2": aq_cur.get("nitrogen_dioxide"),
        "hourly_precip": _hourly(om, "precipitation")[:72],
        "hourly_soil": soil[:72],
        "hourly_temp": _hourly(om, "temperature_2m")[:72],
        "hourly_rh": _hourly(om, "relative_humidity_2m")[:72],
        "hourly_dew": _hourly(om, "dew_point_2m")[:72],
        "hourly_pressure": _hourly(om, "pressure_msl")[:72],
        "hourly_wind": _hourly(om, "wind_speed_10m")[:72],
        "hourly_wind_dir": _hourly(om, "wind_direction_10m")[:72],
        "hourly_gust": _hourly(om, "wind_gusts_10m")[:72],
        "hourly_cloud": _hourly(om, "cloud_cover")[:72],
        "hourly_cloud_low": _hourly(om, "cloud_cover_low")[:72],
        "hourly_cloud_mid": _hourly(om, "cloud_cover_mid")[:72],
        "hourly_cloud_high": _hourly(om, "cloud_cover_high")[:72],
        "hourly_weather_code": _hourly(om, "weather_code")[:72],
        "hourly_cape": _hourly(om, "cape")[:72],
        "hourly_vpd": _hourly(om, "vapour_pressure_deficit")[:72],
        "hourly_prob": _hourly(om, "precipitation_probability")[:72],
        "hourly_us_aqi": _hourly(aq, "us_aqi")[:72],
        "hourly_eu_aqi": _hourly(aq, "european_aqi")[:72],
        "hourly_aqi_times": (aq.get("hourly") or {}).get("time") or [],
        "hourly_times": (om.get("hourly") or {}).get("time") or [],
        "daily_times": daily_times,
        "daily_wind_max": daily_wind_max,
        "daily_wind_dir": daily_wind_dir,
        "wave_height_m": mcur.get("wave_height"),
        "wave_dir_deg": mcur.get("wave_direction"),
        "wave_period_s": mcur.get("wave_period"),
        "hourly_wave": wave_vals,
        "hourly_wave_dir": _hourly(marine, "wave_direction")[:72],
        "hourly_wave_times": (marine.get("hourly") or {}).get("time") or [],
        "marine_inland": inland,
    }

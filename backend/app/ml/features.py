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


def _parse_hour(ts: str) -> datetime | None:
    if not ts:
        return None
    try:
        t = str(ts).replace("Z", "")
        if "T" not in t:
            if len(t) >= 10 and t[4:5] == "-":
                t = t[:10] + "T00:00:00"
            else:
                return None
        dt = datetime.fromisoformat(t[:19])
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=IST)
        return dt
    except ValueError:
        return None


def hourly_now_index(times: list, now: datetime | None = None) -> int:
    """Last hourly slot at or before now (IST). 0 if times are not ISO (tests)."""
    now = now or datetime.now(IST)
    last = 0
    found = False
    for i, t in enumerate(times):
        dt = _parse_hour(str(t))
        if dt is None:
            continue
        if dt <= now:
            last = i
            found = True
        elif found:
            break
    return last if found else 0


def past_window(seq: list, now_i: int, n: int) -> list:
    """n values ending at now_i. If now_i is 0 (fixtures / already-now), take seq[:n]."""
    if not seq or n <= 0:
        return []
    i = int(now_i or 0)
    if i <= 0:
        return list(seq[:n])
    a = max(0, i - n + 1)
    return list(seq[a : i + 1])


def from_now(seq: list, now_i: int, n: int) -> list:
    """n values starting at now_i (inclusive)."""
    if not seq or n <= 0:
        return []
    i = max(0, int(now_i or 0))
    return list(seq[i : i + n])


def value_at_now(seq: list, now_i: int, default: float = 0.0) -> float:
    if not seq:
        return default
    i = int(now_i or 0)
    if i < 0:
        i = 0
    if i >= len(seq):
        i = len(seq) - 1
    try:
        v = seq[i]
        return default if v is None else float(v)
    except (TypeError, ValueError):
        return default


def _hourly(om: dict, key: str) -> list[float]:
    """Keep index alignment with hourly time. None → 0.0 (same as _daily)."""
    vals = (om.get("hourly") or {}).get(key) or []
    out = []
    for v in vals:
        try:
            out.append(float(v) if v is not None else 0.0)
        except (TypeError, ValueError):
            out.append(0.0)
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
    hourly_times = list((om.get("hourly") or {}).get("time") or [])
    now_i = hourly_now_index(hourly_times)
    aqi_times = list((aq.get("hourly") or {}).get("time") or [])
    aqi_now_i = hourly_now_index(aqi_times) if aqi_times else 0
    wave_times = list((marine.get("hourly") or {}).get("time") or [])
    wave_now_i = hourly_now_index(wave_times) if wave_times else 0

    precip_3d = sum(precip[:3])
    precip_today = precip[0] if precip else 0.0
    n_h = len(hourly_times)
    win_a = max(0, now_i - 24)
    win_b = min(n_h, now_i + 1 + 48) if n_h else 0
    if n_h and win_b <= win_a:
        win_a, win_b = 0, min(n_h, 72)
    now_i_w = max(0, now_i - win_a) if n_h else 0
    hourly_times_w = hourly_times[win_a:win_b] if n_h else []

    def hw(seq: list) -> list:
        return list(seq[win_a:win_b]) if n_h else list(seq)

    soil_now = value_at_now(soil, now_i, default=0.30) if soil else 0.30

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
    wave_vals = _hourly(marine, "wave_height")
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
        "hourly_precip": hw(_hourly(om, "precipitation")),
        "hourly_soil": hw(soil),
        "hourly_temp": hw(_hourly(om, "temperature_2m")),
        "hourly_rh": hw(_hourly(om, "relative_humidity_2m")),
        "hourly_dew": hw(_hourly(om, "dew_point_2m")),
        "hourly_pressure": hw(_hourly(om, "pressure_msl")),
        "hourly_wind": hw(_hourly(om, "wind_speed_10m")),
        "hourly_wind_dir": hw(_hourly(om, "wind_direction_10m")),
        "hourly_gust": hw(_hourly(om, "wind_gusts_10m")),
        "hourly_cloud": hw(_hourly(om, "cloud_cover")),
        "hourly_cloud_low": hw(_hourly(om, "cloud_cover_low")),
        "hourly_cloud_mid": hw(_hourly(om, "cloud_cover_mid")),
        "hourly_cloud_high": hw(_hourly(om, "cloud_cover_high")),
        "hourly_weather_code": hw(_hourly(om, "weather_code")),
        "hourly_cape": hw(_hourly(om, "cape")),
        "hourly_vpd": hw(_hourly(om, "vapour_pressure_deficit")),
        "hourly_prob": hw(_hourly(om, "precipitation_probability")),
        "hourly_us_aqi": _hourly(aq, "us_aqi"),
        "hourly_eu_aqi": _hourly(aq, "european_aqi"),
        "hourly_aqi_times": aqi_times,
        "hourly_times": hourly_times_w,
        "hourly_now_i": now_i_w,
        "hourly_aqi_now_i": aqi_now_i,
        "hourly_wave_now_i": wave_now_i,
        "wind_now_ms": (float(current["wind_speed_10m"]) / 3.6) if current.get("wind_speed_10m") is not None else None,
        "daily_times": daily_times,
        "daily_wind_max": daily_wind_max,
        "daily_wind_dir": daily_wind_dir,
        "wave_height_m": mcur.get("wave_height"),
        "wave_dir_deg": mcur.get("wave_direction"),
        "wave_period_s": mcur.get("wave_period"),
        "hourly_wave": wave_vals,
        "hourly_wave_dir": _hourly(marine, "wave_direction"),
        "hourly_wave_times": wave_times,
        "marine_inland": inland,
    }

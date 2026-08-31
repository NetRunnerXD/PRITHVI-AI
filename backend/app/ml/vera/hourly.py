"""Canonical hourly series: past 12 h through next 72 h (rain, temp, wind, heat)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from app.science.wbgt import estimate as wbgt_est

IST = timezone(timedelta(hours=5, minutes=30))

PAST_H = 12
FUTURE_H = 72


def _now_hour() -> datetime:
    n = datetime.now(IST).replace(minute=0, second=0, microsecond=0)
    return n


def member_hourly(members: dict[str, dict], h: int, key: str = "hourly_precip") -> dict[str, float]:
    out: dict[str, float] = {}
    for sid, pack in members.items():
        ser = pack.get(key) or (pack.get("precip_hours") if key == "hourly_precip" else []) or []
        if h < len(ser):
            try:
                out[sid] = round(float(ser[h]), 3)
            except (TypeError, ValueError):
                continue
    return out


def _member_scaled(
    members: dict[str, dict],
    h: int,
    hourly_key: str,
    daily_key: str,
    om_hourly: list[float],
    om_daily: list[float],
    now_i: int,
) -> dict[str, float]:
    hit = member_hourly(members, h, hourly_key)
    if hit:
        return hit
    day = 0 if h < now_i else (h - now_i) // 24
    out: dict[str, float] = {}
    om_h = om_hourly[h] if h < len(om_hourly) else None
    om_d = om_daily[day] if day < len(om_daily) else None
    if om_h is None:
        return out
    for sid, pack in members.items():
        dser = pack.get(daily_key) or []
        if day < len(dser) and om_d:
            try:
                scale = float(dser[day]) / float(om_d)
            except (TypeError, ValueError, ZeroDivisionError):
                scale = 1.0
            out[sid] = round(float(om_h) * scale, 3)
        else:
            out[sid] = round(float(om_h), 3)
    return out


def blend_hour(vals: dict[str, float], weights: dict[str, float]) -> float:
    num = den = 0.0
    for sid, v in vals.items():
        w = float(weights.get(sid, 0))
        if w <= 0:
            w = 1.0
        num += v * w
        den += w
    return round(num / den, 3) if den else 0.0


def mean_hour(vals: dict[str, float]) -> float | None:
    if not vals:
        return None
    return round(sum(vals.values()) / len(vals), 3)


def _wbgt(temp_c: float | None, rh: float | None, wind_kmh: float | None) -> float | None:
    if temp_c is None:
        return None
    wb = wbgt_est(temp_c, rh if rh is not None else 70.0, (wind_kmh or 0) / 3.6 if wind_kmh else None)
    return wb.get("wbgt_c")


def build(
    f: dict[str, Any],
    members: dict[str, dict],
    weights: dict[str, float],
    ensemble_hourly: list[float],
    loc_key: str,
) -> list[dict[str, Any]]:
    om_rain = [float(x) for x in (f.get("hourly_precip") or [])]
    om_temp = [float(x) for x in (f.get("hourly_temp") or [])]
    om_wind = [float(x) for x in (f.get("hourly_wind") or [])]
    om_rh = [float(x) for x in (f.get("hourly_rh") or [])]
    times = [str(x) for x in (f.get("hourly_times") or [])]
    now_i = int(f.get("hourly_now_i") or 0)
    tmax_om = [float(x) for x in (f.get("temp_max") or [])]
    wind_om_d = [float(x) for x in (f.get("wind_max") or [])]
    n = max(len(om_rain), len(times), len(om_temp), len(ensemble_hourly), now_i + 1)
    start_i = max(0, now_i - PAST_H)
    end_i = min(n, now_i + FUTURE_H)
    start = _now_hour()
    rows = []
    for i in range(start_i, end_i):
        lead = i - now_i
        t = times[i] if i < len(times) and times[i] else (start + timedelta(hours=lead)).isoformat(timespec="minutes")
        rain_mem = member_hourly(members, i, "hourly_precip")
        temp_mem = _member_scaled(members, i, "hourly_temp", "temp_max", om_temp, tmax_om, now_i)
        wind_mem = _member_scaled(members, i, "hourly_wind", "wind_max", om_wind, wind_om_d, now_i)
        rain_om = om_rain[i] if i < len(om_rain) else None
        temp_om = om_temp[i] if i < len(om_temp) else None
        wind_om = om_wind[i] if i < len(om_wind) else None
        rh = om_rh[i] if i < len(om_rh) else 70.0
        rain_blend = blend_hour(rain_mem, weights) if rain_mem else (rain_om or 0.0)
        rain_ens = ensemble_hourly[i] if i < len(ensemble_hourly) else (mean_hour(rain_mem) if rain_mem else rain_blend)
        temp_blend = blend_hour(temp_mem, weights) if temp_mem else temp_om
        temp_ens = mean_hour(temp_mem) if temp_mem else temp_om
        wind_blend = blend_hour(wind_mem, weights) if wind_mem else wind_om
        wind_ens = mean_hour(wind_mem) if wind_mem else wind_om
        rows.append(
            {
                "t": t,
                "lead_h": lead,
                "ensemble": round(float(rain_ens), 3),
                "moe": round(float(rain_blend), 3),
                "om": round(float(rain_om), 3) if rain_om is not None else None,
                "ensemble_temp_c": round(float(temp_ens), 1) if temp_ens is not None else None,
                "moe_temp_c": round(float(temp_blend), 1) if temp_blend is not None else None,
                "om_temp_c": round(float(temp_om), 1) if temp_om is not None else None,
                "ensemble_wind_kmh": round(float(wind_ens), 1) if wind_ens is not None else None,
                "moe_wind_kmh": round(float(wind_blend), 1) if wind_blend is not None else None,
                "om_wind_kmh": round(float(wind_om), 1) if wind_om is not None else None,
                "ensemble_wbgt_c": _wbgt(temp_ens, rh, wind_ens),
                "moe_wbgt_c": _wbgt(temp_blend, rh, wind_blend),
                "om_wbgt_c": _wbgt(temp_om, rh, wind_om),
                "members": rain_mem,
                "pin": loc_key,
            }
        )
    return rows

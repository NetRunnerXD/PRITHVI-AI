"""7-day intra-hour pack. Minute rain integrates to the locked hourly millimetres."""

from __future__ import annotations

import math
from datetime import datetime, timedelta, timezone
from typing import Any

from app.science.wbgt import estimate as wbgt_est

IST = timezone(timedelta(hours=5, minutes=30))
WD = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")


def _f(x: Any, default: float = 0.0) -> float:
    try:
        return default if x is None else float(x)
    except (TypeError, ValueError):
        return default


def _skew_weights(n: int) -> list[float]:
    raw = []
    for i in range(n):
        x = (i + 0.5) / n
        t = x - 0.35
        s = 0.18 if t < 0 else 0.32
        raw.append(math.exp(-0.5 * (t / s) ** 2))
    tot = sum(raw) or 1.0
    return [v / tot for v in raw]


def _parse(t: str) -> datetime | None:
    try:
        dt = datetime.fromisoformat(str(t).replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=IST)
        return dt
    except ValueError:
        return None


def _heat_level(tmax: float | None, clim: float) -> str:
    if tmax is None:
        return "No alert"
    if tmax >= 40 or (clim and tmax >= clim + 4.5):
        return "Warning" if tmax >= 42 else "Possible"
    return "No alert"


def _thunder(code: float) -> str | None:
    c = int(code)
    if c >= 95:
        return "thunder"
    if c >= 80:
        return "shower"
    if c >= 61:
        return "rain"
    return None


def _lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * t


def run(
    f: dict[str, Any],
    blend_hourly: list[float] | None = None,
    ensemble_hourly: list[float] | None = None,
) -> dict[str, Any]:
    times = [str(x) for x in (f.get("hourly_times") or [])]
    rain = [_f(x) for x in (f.get("hourly_precip") or [])]
    temp = [_f(x) for x in (f.get("hourly_temp") or [])]
    wind = [_f(x) for x in (f.get("hourly_wind") or [])]
    gust = [_f(x) for x in (f.get("hourly_gust") or f.get("hourly_wind") or [])]
    rh = [_f(x, 70) for x in (f.get("hourly_rh") or [])] or [70.0] * len(rain)
    code = [_f(x) for x in (f.get("hourly_weather_code") or [])]
    blend = [float(x) for x in (blend_hourly or [])]
    ens = [float(x) for x in (ensemble_hourly or [])]
    n = min(len(times), max(len(rain), 1))
    n = min(n, 24 * 8)
    clim = float(f.get("clim_tmax_c") or 35.0)
    dts = [_parse(t) for t in times[:n]]
    by_date: dict[str, list[int]] = {}
    for i, dt in enumerate(dts):
        if dt is None:
            continue
        d = dt.astimezone(IST).date().isoformat()
        by_date.setdefault(d, []).append(i)
    dates = sorted(by_date)[:8]
    days = []
    for di, date in enumerate(dates):
        idxs = by_date[date]
        hours = []
        peak_i = idxs[0]
        peak_r = -1.0
        for i in idxs:
            r = rain[i] if i < len(rain) else 0.0
            if r > peak_r:
                peak_r, peak_i = r, i
            tc = temp[i] if i < len(temp) else None
            rh_i = rh[i] if i < len(rh) else 70.0
            w_i = wind[i] if i < len(wind) else 0.0
            wb = wbgt_est(tc or 30.0, rh_i, w_i / 3.6 if w_i else None) if tc is not None else None
            hours.append(
                {
                    "t": times[i] if i < len(times) else None,
                    "rain_mm": round(r, 2),
                    "website_mm": round(r, 2),
                    "blend_mm": round(blend[i], 2) if i < len(blend) else None,
                    "ensemble_mm": round(ens[i], 2) if i < len(ens) else None,
                    "temp_c": round(tc, 1) if tc is not None else None,
                    "wind_kmh": round(w_i, 1),
                    "gust_kmh": round(gust[i], 1) if i < len(gust) else None,
                    "rh": round(rh_i, 0),
                    "wbgt_c": wb.get("wbgt_c") if wb else None,
                    "heat": wb.get("level") if wb else None,
                    "weather_code": int(code[i]) if i < len(code) else None,
                    "class": _thunder(code[i] if i < len(code) else 0),
                }
            )
        tmax = max((h["temp_c"] for h in hours if h["temp_c"] is not None), default=None)
        tmin = min((h["temp_c"] for h in hours if h["temp_c"] is not None), default=None)
        peak_zoom = _hour_minutes(
            rain[peak_i] if peak_i < len(rain) else 0.0,
            temp[peak_i] if peak_i < len(temp) else 30.0,
            temp[peak_i + 1] if peak_i + 1 < len(temp) else (temp[peak_i] if peak_i < len(temp) else 30.0),
            wind[peak_i] if peak_i < len(wind) else 0.0,
            wind[peak_i + 1] if peak_i + 1 < len(wind) else 0.0,
            rh[peak_i] if peak_i < len(rh) else 70.0,
            times[peak_i] if peak_i < len(times) else date,
            stride_min=5,
            blend_mm=blend[peak_i] if peak_i < len(blend) else None,
            ensemble_mm=ens[peak_i] if peak_i < len(ens) else None,
        )
        wd = None
        if idxs and dts[idxs[0]]:
            wd = WD[dts[idxs[0]].astimezone(IST).weekday()]
        days.append(
            {
                "date": date,
                "weekday": wd,
                "label": f"Day {di + 1}",
                "offset": di,
                "rain_mm": round(sum(h["rain_mm"] or 0 for h in hours), 2),
                "tmax_c": tmax,
                "tmin_c": tmin,
                "wind_max_kmh": max((h["wind_kmh"] or 0) for h in hours) if hours else None,
                "heat_level": _heat_level(tmax, clim),
                "thunder_hint": next((h["class"] for h in hours if h.get("class") in {"thunder", "shower"}), None),
                "hours": hours,
                "peak_hour": times[peak_i] if peak_i < len(times) else None,
                "peak_minutes": peak_zoom,
            }
        )
    minutes_today = []
    if days:
        today = days[0]
        for i, h in enumerate(today["hours"][:24]):
            nxt_t = today["hours"][i + 1]["temp_c"] if i + 1 < len(today["hours"]) else h["temp_c"]
            nxt_w = today["hours"][i + 1]["wind_kmh"] if i + 1 < len(today["hours"]) else h["wind_kmh"]
            minutes_today.extend(
                _hour_minutes(
                    h["rain_mm"] or 0,
                    h["temp_c"] or 30,
                    nxt_t or h["temp_c"] or 30,
                    h["wind_kmh"] or 0,
                    nxt_w or 0,
                    h["rh"] or 70,
                    h["t"] or today["date"],
                    stride_min=15,
                    blend_mm=h.get("blend_mm"),
                    ensemble_mm=h.get("ensemble_mm"),
                )
            )
        days[0]["minutes_today"] = minutes_today
    return {
        "note": "Minute rain integrates to the Open-Meteo hourly millimetres. Temp/wind are interpolated between hours. Not a radar nowcast.",
        "stride_today_min": 15,
        "stride_peak_min": 5,
        "days": days,
    }


def _hour_minutes(
    rain_mm: float,
    t0: float,
    t1: float,
    w0: float,
    w1: float,
    rh: float,
    t_iso: str,
    stride_min: int = 5,
    blend_mm: float | None = None,
    ensemble_mm: float | None = None,
) -> list[dict[str, Any]]:
    n = max(1, 60 // stride_min)
    wts = _skew_weights(n)
    start = _parse(t_iso) or datetime.now(IST)
    out = []
    acc = 0.0
    for i, wt in enumerate(wts):
        frac = (i + 0.5) / n
        mm = rain_mm * wt
        acc += mm
        rate = mm * (60 / stride_min)
        bmm = (blend_mm if blend_mm is not None else rain_mm) * wt
        emm = (ensemble_mm if ensemble_mm is not None else rain_mm) * wt
        tc = _lerp(t0, t1, frac)
        wc = _lerp(w0, w1, frac)
        wb = wbgt_est(tc, rh, wc / 3.6 if wc else None)
        ts = start + timedelta(minutes=i * stride_min)
        out.append(
            {
                "t": ts.isoformat(timespec="minutes"),
                "rain_mm": round(mm, 3),
                "rain_mm_h": round(rate, 2),
                "website_mm_h": round(rate, 2),
                "blend_mm_h": round(bmm * (60 / stride_min), 2),
                "ensemble_mm_h": round(emm * (60 / stride_min), 2),
                "temp_c": round(tc, 1),
                "wind_kmh": round(wc, 1),
                "wbgt_c": wb["wbgt_c"],
                "acc_mm": round(acc, 3),
            }
        )
    return out

"""7-day intra-hour pack. Minute rain integrates to the locked hourly millimetres."""

from __future__ import annotations

import math
from datetime import date, datetime, timedelta, timezone
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


def _relative_label(d: date, today: date) -> str:
    delta = (d - today).days
    if delta == -1:
        return "Yesterday"
    if delta == 0:
        return "Today"
    if delta == 1:
        return "Tomorrow"
    if delta > 1:
        return f"In {delta} days"
    return f"{abs(delta)} days ago"


def run(
    f: dict[str, Any],
    blend_hourly: list[float] | None = None,
    ensemble_hourly: list[float] | None = None,
    hourly_rows: list[dict[str, Any]] | None = None,
    today: date | None = None,
) -> dict[str, Any]:
    today = today or datetime.now(IST).date()
    if hourly_rows:
        return _from_rows(hourly_rows, f, today)
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
    for date_s in dates:
        idxs = by_date[date_s]
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
                    "blend_temp_c": None,
                    "ensemble_temp_c": None,
                    "wind_kmh": round(w_i, 1),
                    "blend_wind_kmh": None,
                    "ensemble_wind_kmh": None,
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
            times[peak_i] if peak_i < len(times) else date_s,
            stride_min=5,
            blend_mm=blend[peak_i] if peak_i < len(blend) else None,
            ensemble_mm=ens[peak_i] if peak_i < len(ens) else None,
        )
        wd = None
        if idxs and dts[idxs[0]]:
            wd = WD[dts[idxs[0]].astimezone(IST).weekday()]
        day_d = date.fromisoformat(date_s) if len(date_s) >= 10 else today
        days.append(
            {
                "date": date_s,
                "weekday": wd,
                "label": _relative_label(day_d, today),
                "offset": (day_d - today).days,
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
    _attach_minutes(days)
    return {
        "note": "Same Ensemble / Blend / Website hours as the Hourly tab. Minute rain integrates to the locked hourly millimetres.",
        "stride_today_min": 15,
        "stride_peak_min": 5,
        "days": days,
        "horizon_h": 72,
    }


def _row_hour(r: dict[str, Any]) -> dict[str, Any]:
    return {
        "t": r.get("t"),
        "lead_h": r.get("lead_h"),
        "rain_mm": r.get("om"),
        "website_mm": r.get("om"),
        "blend_mm": r.get("moe"),
        "ensemble_mm": r.get("ensemble"),
        "temp_c": r.get("om_temp_c"),
        "blend_temp_c": r.get("moe_temp_c"),
        "ensemble_temp_c": r.get("ensemble_temp_c"),
        "wind_kmh": r.get("om_wind_kmh"),
        "blend_wind_kmh": r.get("moe_wind_kmh"),
        "ensemble_wind_kmh": r.get("ensemble_wind_kmh"),
        "wbgt_c": r.get("om_wbgt_c"),
        "blend_wbgt_c": r.get("moe_wbgt_c"),
        "ensemble_wbgt_c": r.get("ensemble_wbgt_c"),
        "rh": 70,
    }


def _from_rows(hourly_rows: list[dict[str, Any]], f: dict[str, Any], today: date) -> dict[str, Any]:
    clim = float(f.get("clim_tmax_c") or 35.0)
    by_date: dict[str, list[dict[str, Any]]] = {}
    horizon = []
    for r in hourly_rows:
        lead = int(r.get("lead_h") or 0)
        if lead < -24 or lead >= 72:
            continue
        dt = _parse(str(r.get("t") or ""))
        if dt is None:
            continue
        d = dt.astimezone(IST).date()
        hour = _row_hour(r)
        by_date.setdefault(d.isoformat(), []).append(hour)
        if 0 <= lead < 72:
            horizon.append(hour)
    days = []
    for date_s in sorted(by_date):
        hours = by_date[date_s]
        peak = max(hours, key=lambda h: float(h.get("blend_mm") or h.get("rain_mm") or 0), default=hours[0])
        tmax = max((h["temp_c"] for h in hours if h.get("temp_c") is not None), default=None)
        tmin = min((h["temp_c"] for h in hours if h.get("temp_c") is not None), default=None)
        dt0 = _parse(hours[0]["t"]) if hours else None
        day_d = date.fromisoformat(date_s)
        peak_i = hours.index(peak) if peak in hours else 0
        nxt = hours[peak_i + 1] if peak_i + 1 < len(hours) else peak
        peak_zoom = _hour_minutes(
            float(peak.get("rain_mm") or 0),
            float(peak.get("temp_c") or 30),
            float(nxt.get("temp_c") or peak.get("temp_c") or 30),
            float(peak.get("wind_kmh") or 0),
            float(nxt.get("wind_kmh") or 0),
            70.0,
            str(peak.get("t") or date_s),
            stride_min=5,
            blend_mm=peak.get("blend_mm"),
            ensemble_mm=peak.get("ensemble_mm"),
        )
        days.append(
            {
                "date": date_s,
                "weekday": WD[dt0.astimezone(IST).weekday()] if dt0 else None,
                "label": _relative_label(day_d, today),
                "offset": (day_d - today).days,
                "rain_mm": round(sum(float(h.get("blend_mm") or h.get("rain_mm") or 0) for h in hours), 2),
                "tmax_c": tmax,
                "tmin_c": tmin,
                "wind_max_kmh": max((h.get("blend_wind_kmh") or h.get("wind_kmh") or 0) for h in hours) if hours else None,
                "heat_level": _heat_level(tmax, clim),
                "hours": hours,
                "peak_hour": peak.get("t"),
                "peak_minutes": peak_zoom,
            }
        )
    _attach_minutes(days)
    return {
        "note": "Same Ensemble / Blend / Website hours as Hourly, Extremes, and Compare. Blend vs website for the next 72 hours.",
        "stride_today_min": 15,
        "stride_peak_min": 5,
        "days": days,
        "horizon_h": 72,
        "horizon": horizon,
    }


def _attach_minutes(days: list[dict[str, Any]]) -> None:
    today_day = next((d for d in days if d.get("label") == "Today"), days[0] if days else None)
    if not today_day:
        return
    minutes_today = []
    hours = today_day.get("hours") or []
    for i, h in enumerate(hours[:24]):
        nxt = hours[i + 1] if i + 1 < len(hours) else h
        minutes_today.extend(
            _hour_minutes(
                h.get("rain_mm") or 0,
                h.get("temp_c") or 30,
                nxt.get("temp_c") or h.get("temp_c") or 30,
                h.get("wind_kmh") or 0,
                nxt.get("wind_kmh") or 0,
                h.get("rh") or 70,
                h.get("t") or today_day["date"],
                stride_min=15,
                blend_mm=h.get("blend_mm"),
                ensemble_mm=h.get("ensemble_mm"),
            )
        )
    today_day["minutes_today"] = minutes_today


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

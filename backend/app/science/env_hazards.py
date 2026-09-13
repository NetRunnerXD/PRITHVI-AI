"""Fog, IMD heatwave, and WHO UV nowcast heads.

Numbers stay off the LLM. Does not rewrite locked Open-Meteo millimetres.
Windows are IST clock bounds: expected start → expected end.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from app.data.physiography import classify
from app.science.nowcast import _clip
from app.science.wbgt import estimate as wbgt_est

IST = timezone(timedelta(hours=5, minutes=30))

# Indo-Gangetic Plain winter radiation-fog prior (WiFEX). Labelled climatology, not vis.
IGP_STATES = {
    "Punjab",
    "Haryana",
    "Delhi",
    "Chandigarh",
    "Uttar Pradesh",
    "Bihar",
    "West Bengal",
    "Uttarakhand",
    "Rajasthan",
    "Madhya Pradesh",
}

# IMD visibility classes (metres).
FOG_VERY_DENSE = 50
FOG_DENSE = 200
FOG_MODERATE = 500
FOG_SHALLOW = 1000

# WHO UV Index.
UVI_HIGH = 6
UVI_VERY_HIGH = 8
UVI_EXTREME = 11


def _iso(dt: datetime) -> str:
    return dt.astimezone(IST).isoformat(timespec="minutes")


def _now() -> datetime:
    return datetime.now(IST)


def _clip01(x: float) -> float:
    return max(0.0, min(1.0, float(x)))


def _series(f: dict[str, Any], key: str) -> list[float | None]:
    raw = f.get(key) or []
    out: list[float | None] = []
    for v in raw:
        if v is None:
            out.append(None)
            continue
        try:
            out.append(float(v))
        except (TypeError, ValueError):
            out.append(None)
    return out


def _times(f: dict[str, Any]) -> list[str]:
    return [str(x) for x in (f.get("hourly_times") or [])]


def _now_i(f: dict[str, Any], n: int) -> int:
    i = int(f.get("hourly_now_i") or 0)
    return max(0, min(i, max(0, n - 1)))


def _parse_hour(raw: str | None, fallback: datetime) -> datetime:
    if not raw:
        return fallback
    try:
        t = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
        if t.tzinfo is None:
            t = t.replace(tzinfo=IST)
        return t.astimezone(IST)
    except ValueError:
        return fallback


def _contiguous_window(
    times: list[str],
    mask: list[bool],
    now: datetime,
) -> tuple[datetime | None, datetime | None]:
    start = end = None
    for i, hit in enumerate(mask):
        if not hit:
            if start is not None and end is not None:
                break
            continue
        t = _parse_hour(times[i] if i < len(times) else None, now + timedelta(hours=i))
        if start is None:
            start = t
        end = t + timedelta(hours=1)
    return start, end


def _fog_grade(vis_m: float | None) -> str:
    if vis_m is None:
        return "none"
    v = float(vis_m)
    if v < FOG_VERY_DENSE:
        return "very_dense"
    if v < FOG_DENSE:
        return "dense"
    if v < FOG_MODERATE:
        return "moderate"
    if v < FOG_SHALLOW:
        return "shallow"
    return "none"


def fog_nowcast(
    f: dict[str, Any],
    *,
    loc: Any = None,
    bands: dict[str, Any] | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    """IMD-class fog from OM vis + dewpoint + WiFEX radiation-fog prior + optional INSAT BTD."""
    now = now or _now()
    vis = _series(f, "hourly_vis")
    rh = _series(f, "hourly_rh")
    dew = _series(f, "hourly_dew")
    temp = _series(f, "hourly_temp")
    wind = _series(f, "hourly_wind")
    code = _series(f, "hourly_weather_code")
    is_day = _series(f, "hourly_is_day")
    times = _times(f)
    n = max(len(vis), len(rh), 1)
    i0 = _now_i(f, n)

    def at(ser: list[float | None], i: int) -> float | None:
        return ser[i] if i < len(ser) else None

    vis0 = at(vis, i0)
    rh0 = at(rh, i0)
    dew0 = at(dew, i0)
    t0 = at(temp, i0)
    w0 = at(wind, i0)
    c0 = at(code, i0)
    day0 = at(is_day, i0)
    dep = (t0 - dew0) if t0 is not None and dew0 is not None else None

    p = 0.04
    if vis0 is not None and vis0 < 1000:
        p += 0.38
    if vis0 is not None and vis0 < 200:
        p += 0.22
    if rh0 is not None and rh0 >= 90:
        p += 0.14
    if dep is not None and dep <= 2.0:
        p += 0.18
    if w0 is not None and w0 < 8:
        p += 0.10
    if c0 is not None and 45 <= c0 <= 49:
        p += 0.32
    if day0 == 0:
        p += 0.08

    state = getattr(loc, "state", None) if loc is not None else f.get("state")
    month = now.month
    igp = (state or "") in IGP_STATES and month in {11, 12, 1, 2}
    if igp and (day0 == 0 or (now.hour >= 22 or now.hour <= 9)):
        p += 0.08

    btd = None
    vis_gray = None
    if isinstance(bands, dict):
        mir = tir = visb = None
        for b in bands.get("bands") or []:
            if not isinstance(b, dict) or not b.get("ok"):
                continue
            name = str(b.get("channel") or "")
            tb = b.get("tb_k")
            if name.startswith("MIR"):
                mir = tb
            elif name.startswith("TIR") or "10.8" in name:
                tir = tb
            elif name.startswith("VIS"):
                visb = b.get("gray")
        if mir is not None and tir is not None:
            try:
                btd = float(tir) - float(mir)
            except (TypeError, ValueError):
                btd = None
        vis_gray = visb
        if day0 == 0 and btd is not None and 0.5 <= btd <= 12:
            p += 0.12
        if day0 == 1 and vis_gray is not None and float(vis_gray) >= 90 and (t0 is None or t0 < 18):
            p += 0.08

    p = min(0.98, p)
    grade = _fog_grade(vis0)
    hours_fwd = min(24, n - i0)
    mask = []
    for k in range(hours_fwd):
        i = i0 + k
        v = at(vis, i)
        c = at(code, i)
        hit = (v is not None and v < 1000) or (c is not None and 45 <= c <= 49)
        mask.append(bool(hit))
    w_times = times[i0 : i0 + hours_fwd] if times else []
    start, end = _contiguous_window(w_times, mask, now)
    if start is None and p >= 0.45:
        start = now.replace(minute=0, second=0, microsecond=0)
        if now.hour >= 16:
            start = start.replace(hour=22)
        end = (start + timedelta(hours=10)).replace(hour=9, minute=0)
        if end <= start:
            end = start + timedelta(hours=8)

    alert = grade in {"dense", "very_dense"} or (p >= 0.55 and vis0 is not None and vis0 < 500)
    level = "warning" if alert else ("watch" if p >= 0.35 or grade == "moderate" else "quiet")
    return {
        "kind": "fog",
        "p_fog": round(p, 3),
        "grade": grade,
        "level": level,
        "alert": alert,
        "vis_m": None if vis0 is None else round(vis0, 0),
        "dewpoint_depression_c": None if dep is None else round(dep, 2),
        "rh_pct": rh0,
        "wind_kmh": w0,
        "igp_prior": igp,
        "btd_k": None if btd is None else round(btd, 2),
        "window_start": _iso(start) if start else None,
        "window_end": _iso(end) if end else None,
        "method": "OM vis + dewpoint + WMO 45–49 + WiFEX IGP prior + INSAT MIR−TIR BTD",
        "note": "Visibility from Open-Meteo. INSAT BTD is a JPEG proxy, not MOSDAC L2 fog.",
    }


def _heat_threshold(kind: str, coast_km: float | None) -> tuple[float, str]:
    if kind == "orographic":
        return 30.0, "hills"
    if kind in {"coast", "hugli", "delta", "island"} or (coast_km is not None and float(coast_km) <= 40):
        return 37.0, "coast"
    return 40.0, "plains"


def heatwave_nowcast(
    f: dict[str, Any],
    *,
    loc: Any = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    """IMD dry-bulb heatwave + WBGT humid-heat. Dual head, labelled separately."""
    now = now or _now()
    tmax = [float(x) for x in (f.get("temp_max") or f.get("tmax") or [])[:7] if x is not None]
    tmin = [float(x) for x in (f.get("temp_min") or f.get("tmin") or [])[:7] if x is not None]
    times = [str(x) for x in (f.get("daily_times") or [])[:7]]
    clim = float(f.get("clim_tmax_c") or 35.0)
    coast_km = f.get("coast_km")
    try:
        coast_km_f = float(coast_km) if coast_km is not None else None
    except (TypeError, ValueError):
        coast_km_f = None
    phys = classify(
        float(getattr(loc, "lat", 0) or f.get("lat") or 0),
        float(getattr(loc, "lon", 0) or f.get("lon") or 0),
        loc=loc,
        coast_km=coast_km_f,
    )
    thresh, zone = _heat_threshold(str(phys.get("kind") or "plains"), coast_km_f)

    days: list[dict[str, Any]] = []
    for i, tx in enumerate(tmax):
        dep = tx - clim
        abs_hw = tx >= 45.0
        abs_sev = tx >= 47.0
        dep_hw = tx >= thresh and 4.5 <= dep < 6.5
        dep_sev = tx >= thresh and dep >= 6.5
        hit = abs_hw or dep_hw or abs_sev or dep_sev
        sev = abs_sev or dep_sev
        days.append(
            {
                "i": i,
                "date": times[i] if i < len(times) else None,
                "tmax_c": round(tx, 1),
                "departure_c": round(dep, 1),
                "heatwave": hit,
                "severe": sev,
            }
        )

    best_run = 0
    run = 0
    best_span: tuple[int, int] | None = None
    cur_start = 0
    for i, d in enumerate(days):
        if d["heatwave"]:
            if run == 0:
                cur_start = i
            run += 1
            if run > best_run:
                best_run = run
                best_span = (cur_start, i)
        else:
            run = 0
    qualifies = best_run >= 2
    severe = qualifies and any(days[i]["severe"] for i in range(best_span[0], best_span[1] + 1) if best_span)

    hourly_t = _series(f, "hourly_temp")
    hourly_rh = _series(f, "hourly_rh")
    hourly_wind = _series(f, "hourly_wind")
    hourly_times = _times(f)
    i0 = _now_i(f, len(hourly_t))
    wbgt_hours: list[bool] = []
    wbgt_vals: list[float] = []
    peak_wbgt = None
    for k, t in enumerate(hourly_t[i0 : i0 + 24]):
        if t is None:
            wbgt_hours.append(False)
            continue
        rh = hourly_rh[i0 + k] if i0 + k < len(hourly_rh) and hourly_rh[i0 + k] is not None else 50.0
        wind = hourly_wind[i0 + k] if i0 + k < len(hourly_wind) else None
        wind_ms = (float(wind) / 3.6) if wind is not None else None
        w = wbgt_est(float(t), float(rh), wind_ms)
        val = float(w.get("wbgt_c") or 0)
        wbgt_vals.append(val)
        wbgt_hours.append(val >= 28.0)
        if peak_wbgt is None or val > peak_wbgt:
            peak_wbgt = val
    humid = sum(1 for h in wbgt_hours if h) >= 2
    humid_stop = any(v >= 32 for v in wbgt_vals)

    start = end = None
    if qualifies and best_span is not None:
        d0 = days[best_span[0]].get("date")
        d1 = days[best_span[1]].get("date")
        try:
            s = datetime.fromisoformat(str(d0)).replace(hour=11, minute=0, tzinfo=IST)
            e = datetime.fromisoformat(str(d1)).replace(hour=16, minute=0, tzinfo=IST)
            start, end = s, e
        except (TypeError, ValueError):
            start = now.replace(hour=11, minute=0, second=0, microsecond=0)
            end = start + timedelta(days=max(0, best_run - 1), hours=5)
    elif humid:
        fwd_times = hourly_times[i0 : i0 + 24]
        day_mask: list[bool] = []
        for k, hit in enumerate(wbgt_hours):
            t = _parse_hour(fwd_times[k] if k < len(fwd_times) else None, now + timedelta(hours=k))
            day_mask.append(bool(hit and 9 <= t.hour <= 17))
        start, end = _contiguous_window(fwd_times, day_mask if any(day_mask) else wbgt_hours, now)
        if start is None:
            start = now.replace(hour=11, minute=0, second=0, microsecond=0)
            end = start.replace(hour=16)

    p = 0.05
    if qualifies:
        p = 0.72 if severe else 0.55
    elif any(d["heatwave"] for d in days[:1]):
        p = 0.35
    if humid:
        p = max(p, 0.48)
    if humid_stop:
        p = max(p, 0.70)

    alert = qualifies or humid_stop or (humid and (peak_wbgt or 0) >= 30)
    level = "warning" if alert else ("watch" if p >= 0.28 else "quiet")
    tmax0 = tmax[0] if tmax else None
    return {
        "kind": "heatwave",
        "p": round(_clip01(p), 3),
        "level": level,
        "alert": alert,
        "imd_qualifies": qualifies,
        "imd_severe": bool(severe),
        "zone": zone,
        "threshold_c": thresh,
        "tmax_c": tmax0,
        "clim_tmax_c": clim,
        "consecutive": best_run,
        "days_ge_thresh": sum(1 for d in days if d["heatwave"]),
        "humid_heat": humid,
        "wbgt_peak_c": None if peak_wbgt is None else round(peak_wbgt, 1),
        "wbgt_stop": humid_stop,
        "window_start": _iso(start) if start else None,
        "window_end": _iso(end) if end else None,
        "rule": f"IMD {zone}: Tmax ≥{thresh:.0f} °C and +4.5 °C vs clim, 2 days; or Tmax ≥45/47. WBGT ≥28 limit / ≥32 stop.",
        "method": "IMD dry-bulb + WBGT humid-heat",
        "note": "IMD definition ignores humidity; WBGT head is labelled separately.",
    }


def uv_nowcast(f: dict[str, Any], *, now: datetime | None = None) -> dict[str, Any]:
    """WHO UV Index alert from Open-Meteo air-quality hourly uv_index."""
    now = now or _now()
    uv = _series(f, "hourly_uv")
    times = f.get("hourly_aqi_times") or f.get("hourly_times") or []
    times = [str(x) for x in times]
    i0 = int(f.get("hourly_aqi_now_i") or f.get("hourly_now_i") or 0)
    n = len(uv)
    i0 = max(0, min(i0, max(0, n - 1)))
    uv0 = uv[i0] if i0 < n else None
    daily = f.get("uv_index_max")
    try:
        daily_f = float(daily) if daily is not None else None
    except (TypeError, ValueError):
        daily_f = None
    peak = uv0
    mask: list[bool] = []
    fwd = uv[i0 : i0 + 18]
    for v in fwd:
        hit = v is not None and v >= UVI_VERY_HIGH
        mask.append(bool(hit))
        if v is not None and (peak is None or v > peak):
            peak = v
    if peak is None and daily_f is not None:
        peak = daily_f
    start, end = _contiguous_window([str(t) for t in times[i0 : i0 + 18]], mask, now)
    if start is None and peak is not None and peak >= UVI_VERY_HIGH:
        start = now.replace(hour=10, minute=30, second=0, microsecond=0)
        end = now.replace(hour=15, minute=30, second=0, microsecond=0)
        if end <= start:
            end = start + timedelta(hours=4)

    p = 0.05
    if peak is not None:
        p = _clip01((float(peak) - 3.0) / 9.0)
    extreme = peak is not None and float(peak) >= UVI_EXTREME
    very = peak is not None and float(peak) >= UVI_VERY_HIGH
    alert = bool(very)
    level = "warning" if extreme or very else ("watch" if peak is not None and peak >= UVI_HIGH else "quiet")
    category = "extreme" if extreme else "very_high" if very else "high" if (peak or 0) >= UVI_HIGH else "low"
    return {
        "kind": "uv",
        "p": round(p, 3),
        "level": level,
        "alert": alert,
        "uv_index": None if uv0 is None else round(float(uv0), 1),
        "uv_peak": None if peak is None else round(float(peak), 1),
        "uv_daily_max": daily_f,
        "who_category": category,
        "window_start": _iso(start) if start else None,
        "window_end": _iso(end) if end else None,
        "method": "WHO Global Solar UV Index on Open-Meteo CAMS uv_index",
        "note": "Clear-sky UVI is an upper bound only; alerts use all-sky uv_index.",
    }


def compound_uv_heat(heat: dict[str, Any], uv: dict[str, Any]) -> dict[str, Any] | None:
    """WHO UVI ≥ 8 overlapping WBGT ≥ 28 — one card, two clocks."""
    if not heat.get("humid_heat") and not heat.get("imd_qualifies"):
        return None
    if not uv.get("alert"):
        return None
    if (uv.get("uv_peak") or 0) < UVI_VERY_HIGH:
        return None
    if (heat.get("wbgt_peak_c") or 0) < 28 and not heat.get("imd_qualifies"):
        return None
    return {
        "kind": "uv_heat",
        "alert": True,
        "level": "warning",
        "window_start": uv.get("window_start") or heat.get("window_start"),
        "window_end": uv.get("window_end") or heat.get("window_end"),
        "uv_peak": uv.get("uv_peak"),
        "wbgt_peak_c": heat.get("wbgt_peak_c"),
        "method": "compound WHO UVI ≥ 8 × WBGT ≥ 28",
    }


def convective_window(conv: dict[str, Any] | None, now: datetime | None = None) -> dict[str, Any]:
    """ETA + remaining lifetime → expected start/end for lightning/storm alerts."""
    now = now or _now()
    conv = conv or {}
    light = conv.get("lightning") if isinstance(conv.get("lightning"), dict) else {}
    burst = conv.get("cloudburst") if isinstance(conv.get("cloudburst"), dict) else {}
    cell = conv.get("cell") if isinstance(conv.get("cell"), dict) else {}
    eta = None
    for src in (light.get("nowcast") if isinstance(light.get("nowcast"), dict) else {}, light, burst, cell):
        if isinstance(src, dict) and src.get("eta_min") is not None:
            try:
                eta = float(src["eta_min"])
                break
            except (TypeError, ValueError):
                continue
    remain = None
    if cell.get("remain_min") is not None:
        try:
            remain = float(cell["remain_min"])
        except (TypeError, ValueError):
            remain = None
    if remain is None:
        remain = 40.0
    start = now if eta is None else now + timedelta(minutes=max(0.0, eta))
    end = start + timedelta(minutes=max(12.0, remain))
    return {
        "window_start": _iso(start),
        "window_end": _iso(end),
        "eta_min": eta,
        "remain_min": remain,
    }


def build(
    f: dict[str, Any],
    *,
    loc: Any = None,
    convective: dict[str, Any] | None = None,
    bands: dict[str, Any] | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    now = now or _now()
    fog = fog_nowcast(f, loc=loc, bands=bands, now=now)
    heat = heatwave_nowcast(f, loc=loc, now=now)
    uv = uv_nowcast(f, now=now)
    compound = compound_uv_heat(heat, uv)
    cwin = convective_window(convective, now)
    from app.science.landslide import nowcast as landslide_nowcast

    slide = landslide_nowcast(f, loc=loc, now=now)
    return {
        "fog": fog,
        "heatwave": heat,
        "uv": uv,
        "compound": compound,
        "landslide": slide,
        "convective_window": cwin,
        "as_of": _iso(now),
        "method": "env-hazards-v1",
    }

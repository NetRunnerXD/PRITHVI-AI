"""0–6 h decision nowcast. Numbers stay off the LLM.

Open-Meteo hourly is model analysis/forecast, not a rain-gauge.
Speech and IMD CAP change category and timing only — never millimetres.
"""

from __future__ import annotations

import math
from datetime import datetime, timedelta, timezone
from typing import Any

from app import cache
from app.data.physiography import classify
from app.science.residual import monsoon_regime
from app.science.vernacular import observe_speech

IST = timezone(timedelta(hours=5, minutes=30))


def _clip(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))


def _parse(ts: str) -> datetime | None:
    if not ts:
        return None
    try:
        t = str(ts).replace("Z", "")
        if "T" not in t:
            t = t + "T00:00:00"
        dt = datetime.fromisoformat(t[:19])
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=IST)
        return dt
    except ValueError:
        return None


def _now() -> datetime:
    return datetime.now(IST)


def _xy(lat: float, lon: float, lat0: float, lon0: float) -> tuple[float, float]:
    x = (lon - lon0) * 111.3 * math.cos(math.radians(lat0))
    y = (lat - lat0) * 111.3
    return x, y


def _last_mm(n: dict[str, Any], hour_back: int = 0) -> float | None:
    series = n.get("hourly_precip") or []
    times = n.get("hourly_times") or []
    past, _ = split_hours(times, series)
    if len(past) <= hour_back:
        return None
    return float(past[-(1 + hour_back)]["mm"])


def split_hours(
    times: list[str],
    values: list[float],
    now: datetime | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    now = now or _now()
    past: list[dict[str, Any]] = []
    future: list[dict[str, Any]] = []
    for i, ts in enumerate(times):
        dt = _parse(ts)
        if dt is None:
            continue
        v = float(values[i]) if i < len(values) else 0.0
        row = {"t": ts, "dt": dt, "mm": round(v, 2)}
        if dt <= now:
            past.append(row)
        else:
            future.append(row)
    return past, future


def state_vector(f: dict[str, Any]) -> dict[str, Any]:
    clouds = [float(x) for x in (f.get("hourly_cloud") or [])[:6]]
    winds = [float(x) for x in (f.get("hourly_wind_dir") or [])[:4]]
    rhs = [float(x) for x in (f.get("hourly_rh") or [])[:6]]
    vis = f.get("visibility_m")
    wind_shift = 0.0
    if len(winds) >= 2:
        d = abs(winds[0] - winds[-1]) % 360
        wind_shift = min(d, 360 - d)
    return {
        "cloud_jump": round((clouds[0] - clouds[3]) if len(clouds) >= 4 else 0.0, 1),
        "wind_shift_deg": round(wind_shift, 1),
        "rh_jump": round((rhs[0] - rhs[3]) if len(rhs) >= 4 else 0.0, 1),
        "visibility_km": round(float(vis) / 1000.0, 2) if vis is not None else None,
        "weather_code": f.get("weather_code"),
        "note": "Open-Meteo hourly state, not radar.",
        "method": "multi-variable nowcast state v1",
    }


def regime(
    past: list[dict[str, Any]],
    f: dict[str, Any],
    st: dict[str, Any],
    lat: float | None,
    phys: dict[str, Any] | None = None,
) -> dict[str, Any]:
    last = [p["mm"] for p in past[-3:]] or [0.0]
    mean3 = sum(last) / len(last)
    last1 = last[-1]
    prev = last[-2] if len(last) > 1 else last1
    jump = last1 - prev
    daily = monsoon_regime(f)
    hills = (phys or {}).get("kind") == "orographic" or (lat is not None and 26.2 <= float(lat) <= 27.6)
    if last1 >= 4 or jump >= 2.5:
        name = "cell"
    elif hills and mean3 >= 1.0:
        name = "orographic"
    elif daily == "active" or mean3 >= 2.0:
        name = "monsoon"
    elif st.get("wind_shift_deg", 0) >= 40 and st.get("cloud_jump", 0) >= 15:
        name = "squall"
    elif daily == "break" or (mean3 < 0.3 and last1 < 0.2):
        name = "break"
    else:
        name = "dry"
    return {
        "name": name,
        "daily": daily,
        "mean3_mm": round(mean3, 2),
        "last_mm": round(last1, 2),
        "jump_mm": round(jump, 2),
        "method": "regime-conditioned persistence v1",
    }


def advection(loc: Any, neighbors: list[dict[str, Any]]) -> dict[str, Any]:
    if len(neighbors) < 2:
        return {
            "u_kmh": 0.0,
            "v_kmh": 0.0,
            "speed_kmh": 0.0,
            "upstream_mm": None,
            "n": len(neighbors),
            "method": "no-mesh",
        }
    lat0 = float(getattr(loc, "lat", 0) or 0)
    lon0 = float(getattr(loc, "lon", 0) or 0)

    def mass_xy(hour_back: int) -> tuple[float, float, float]:
        wx = wy = w = 0.0
        for n in neighbors:
            mm = _last_mm(n, hour_back)
            if mm is None or mm <= 0:
                continue
            x, y = _xy(float(n.get("lat") or 0), float(n.get("lon") or 0), lat0, lon0)
            wx += x * mm
            wy += y * mm
            w += mm
        if w <= 0:
            return 0.0, 0.0, 0.0
        return wx / w, wy / w, w

    x0, y0, w0 = mass_xy(0)
    x1, y1, w1 = mass_xy(2)
    if w0 <= 0 or w1 <= 0:
        u = v = 0.0
    else:
        u = (x0 - x1) / 2.0
        v = (y0 - y1) / 2.0
    spd = math.hypot(u, v)
    up_mm = None
    if spd >= 2:
        best = None
        for n in neighbors:
            x, y = _xy(float(n.get("lat") or 0), float(n.get("lon") or 0), lat0, lon0)
            score = -(x * u + y * v)
            last = _last_mm(n, 0) or 0.0
            if best is None or score > best[0]:
                best = (score, last)
        if best:
            up_mm = best[1]
    return {
        "u_kmh": round(u, 2),
        "v_kmh": round(v, 2),
        "speed_kmh": round(spd, 2),
        "upstream_mm": up_mm,
        "n": len(neighbors),
        "method": "gazetteer optical flow v1",
    }


def stream_pair(loc: Any, neighbors: list[dict[str, Any]], adv: dict[str, Any]) -> dict[str, Any]:
    u = float(adv.get("u_kmh") or 0)
    v = float(adv.get("v_kmh") or 0)
    spd = float(adv.get("speed_kmh") or 0)
    if spd < 2 or not neighbors:
        return {"upstream": None, "downstream": None, "eta_h": None, "method": "no-flow"}
    lat0 = float(getattr(loc, "lat", 0) or 0)
    lon0 = float(getattr(loc, "lon", 0) or 0)
    up = dn = None
    for n in neighbors:
        x, y = _xy(float(n.get("lat") or 0), float(n.get("lon") or 0), lat0, lon0)
        along = x * u + y * v
        km = math.hypot(x, y)
        row = {
            "id": n.get("id"),
            "district": n.get("district"),
            "mm": _last_mm(n, 0),
            "km": round(km, 1),
            "along": round(along, 2),
        }
        if along < 0 and (up is None or along < up["along"]):
            up = row
        if along > 0 and (dn is None or along > dn["along"]):
            dn = row
    eta = None
    if up and up["km"] and spd:
        eta = round(up["km"] / spd, 2)
    return {"upstream": up, "downstream": dn, "eta_h": eta, "method": "gazetteer upstream/downstream v1"}


def neighbor_storm(neighbors: list[dict[str, Any]], past: list[dict[str, Any]]) -> dict[str, Any]:
    home = past[-1]["mm"] if past else 0.0
    last_n = [m for m in (_last_mm(n, 0) for n in neighbors) if m is not None]
    wet_n = sum(1 for x in last_n if x >= 0.4)
    flag = wet_n >= 2 and home < 0.2
    return {
        "flag": flag,
        "wet_neighbors": wet_n,
        "n": len(last_n),
        "home_mm": round(home, 2),
        "method": "gazetteer neighbor disagreement v1",
        "note": "Upstream wet / home dry is a storm flag, not extra millimetres.",
    }


def neighborhood_skill(neighbors: list[dict[str, Any]], past: list[dict[str, Any]]) -> dict[str, Any]:
    home = past[-1]["mm"] if past else 0.0
    last_n = [m for m in (_last_mm(n, 0) for n in neighbors) if m is not None]
    return {
        "point_wet": home >= 0.4,
        "neighborhood_wet": any(x >= 0.4 for x in last_n),
        "n": len(last_n),
        "method": "gazetteer neighborhood skill v1",
        "note": "Poor-man's FSS on gazetteer points. Not a radar fractions skill score.",
    }


def _persist_rate(reg: dict[str, Any], last_mm: float, upstream: float | None, lead_h: int) -> float:
    name = reg["name"]
    if name == "break":
        return 0.0
    if name == "cell":
        base = last_mm if lead_h <= 2 else last_mm * (0.55 ** (lead_h - 1))
        if upstream is not None:
            base = 0.55 * base + 0.45 * upstream * (0.7 ** max(0, lead_h - 1))
        return base
    if name == "orographic":
        return last_mm * (0.90 ** lead_h)
    if name == "monsoon":
        return last_mm * (0.92 ** lead_h)
    if name == "squall":
        return last_mm * (0.45 ** lead_h)
    return last_mm * (0.75 ** lead_h)


def cap_prior(caps: list[dict[str, Any]] | None, cap_hit: bool) -> dict[str, Any]:
    blob = " ".join(
        f"{c.get('title') or ''} {c.get('body') or ''}" for c in (caps or [])
    ).lower()
    thunder = any(w in blob for w in ("thunder", "squall", "kal baisakhi", "কালবৈশাখী", "nowcast"))
    heavy = any(w in blob for w in ("heavy", "very heavy", "extremely", "ভারী", "भारी"))
    return {
        "active": bool(cap_hit),
        "thunder": thunder,
        "heavy": heavy,
        "onset_pull": bool(cap_hit and (thunder or heavy)),
        "nwp_weight_delta": -0.08 if (cap_hit and thunder) else 0.0,
        "method": "IMD CAP timing prior v1",
        "note": "CAP changes engine weights and onset, not millimetres.",
    }


def blend_hours(
    past: list[dict[str, Any]],
    future: list[dict[str, Any]],
    reg: dict[str, Any],
    adv: dict[str, Any],
    err_frac: float,
    cap: dict[str, Any],
    hourly_prob: list[float] | None = None,
) -> list[dict[str, Any]]:
    last = past[-1]["mm"] if past else 0.0
    up = adv.get("upstream_mm")
    out: list[dict[str, Any]] = []
    for i, nxt in enumerate(future[:6]):
        lead = i + 1
        nwp = float(nxt["mm"])
        persist = _persist_rate(reg, last, up, lead)
        if lead <= 2:
            engine = "nowcast"
            w_nwp = 0.15
        elif lead <= 4:
            engine = "blend"
            w_nwp = 0.45 + 0.15 * (lead - 3)
        else:
            engine = "nwp"
            w_nwp = 0.85
        w_nwp = _clip(w_nwp + float(cap.get("nwp_weight_delta") or 0), 0.05, 0.95)
        mm = (1 - w_nwp) * persist + w_nwp * nwp
        if lead <= 2:
            mm *= 1.0 + _clip(err_frac, -0.15, 0.15)
        om_p = None
        if hourly_prob and i < len(hourly_prob):
            try:
                om_p = float(hourly_prob[i])
            except (TypeError, ValueError):
                om_p = None
        p_wet = _clip((om_p / 100.0) if om_p is not None else 0.12 + persist / 5.0 + nwp / 8.0, 0.02, 0.95)
        out.append(
            {
                "t": nxt["t"],
                "lead_h": lead,
                "mm": round(max(0.0, mm), 2),
                "nwp_mm": round(nwp, 2),
                "persist_mm": round(max(0.0, persist), 2),
                "p_wet": round(p_wet, 3),
                "engine": engine,
            }
        )
    return out


def onset_cessation(hours: list[dict[str, Any]], pull: bool = False) -> dict[str, Any]:
    start = stop = None
    wet = False
    thresh = 0.2 if pull else 0.4
    for h in hours:
        if not wet and h["mm"] >= thresh:
            start = h["t"]
            wet = True
        elif wet and h["mm"] < 0.2:
            stop = h["t"]
            break
    return {"t_start": start, "t_stop": stop, "pulled": bool(pull and start), "method": "onset/cessation clock v1"}


def kal_baisakhi(
    f: dict[str, Any],
    past: list[dict[str, Any]],
    st: dict[str, Any],
    now: datetime | None = None,
    phys: dict[str, Any] | None = None,
) -> dict[str, Any]:
    now = now or _now()
    hour = now.hour
    month = now.month
    temps = [float(x) for x in (f.get("hourly_temp") or [])[:6]]
    dT = (temps[0] - temps[3]) if len(temps) >= 4 else 0.0
    code = int(f.get("weather_code") or 0)
    belt = bool((phys or {}).get("kal_belt"))
    pre = month in {3, 4, 5, 6}
    if belt and pre:
        score = 8
        if 12 <= hour <= 18:
            score += 20
        if dT >= 2:
            score += 18
        if float(st.get("rh_jump") or 0) >= 8:
            score += 16
        if float(st.get("cloud_jump") or 0) >= 20:
            score += 16
        if float(st.get("wind_shift_deg") or 0) >= 40:
            score += 10
        if past and past[-1]["mm"] >= 1:
            score += 10
        method = "Kal Baisakhi instability proxy v1 (not lightning)"
    else:
        score = 8
        if code >= 95:
            score = 72
        elif code >= 80:
            score = 38
        if st.get("visibility_km") is not None and float(st["visibility_km"]) < 2:
            score += 15
        method = "storm watch from sky code — not Kal Baisakhi"
    score = int(_clip(score, 0, 95))
    return {
        "score_pct": score,
        "level": "watch" if score >= 55 else "quiet",
        "dT_c": round(dT, 2),
        "kal_belt": belt,
        "method": method,
        "note": "Watch only. Does not add millimetres.",
    }


def ponding(hours: list[dict[str, Any]], hy: dict[str, Any], phys: dict[str, Any] | None = None) -> dict[str, Any]:
    rain60 = sum(h["mm"] for h in hours[:1])
    rain120 = sum(h["mm"] for h in hours[:2])
    mem = float(hy.get("memory") or 0.4)
    wet = hy.get("limb") == "wetting" or hy.get("flip") == "runoff"
    factor = 0.25 + 0.65 * mem if wet else 0.08 + 0.12 * mem
    scale = float((phys or {}).get("pond_scale") or 1.0)
    factor = factor * scale
    return {
        "mm_60": round(rain60 * factor, 2),
        "mm_120": round(rain120 * factor, 2),
        "factor": round(factor, 3),
        "limb": hy.get("limb"),
        "phys": (phys or {}).get("kind"),
        "method": "hysteresis ponding v2 (region scale)",
    }


def hourly_budget(hours: list[dict[str, Any]], hy: dict[str, Any]) -> dict[str, Any]:
    mem = float(hy.get("memory") or 0.4)
    wet = hy.get("limb") == "wetting" or hy.get("flip") == "runoff"
    infil_eff = _clip(0.38 + 0.20 * (1 - mem) if wet else 0.70 + 0.18 * (1 - mem), 0.2, 0.95)
    rows = []
    for h in hours[:6]:
        p = float(h["mm"])
        infil = p * infil_eff
        pond = p - infil
        rows.append(
            {
                "t": h["t"],
                "precip_mm": p,
                "infil_mm": round(infil, 2),
                "pond_mm": round(pond, 2),
                "checksum_mm": round(p - infil - pond, 3),
            }
        )
    return {"hours": rows, "infil_eff": round(infil_eff, 3), "method": "hourly water-balance identity v1"}


def tide_rain(
    hours: list[dict[str, Any]],
    coast_km: float | None,
    lon: float | None,
    wave_m: float | None,
    now: datetime | None = None,
    phys: dict[str, Any] | None = None,
) -> dict[str, Any]:
    now = now or _now()
    hugli = bool((phys or {}).get("show_tide") or (phys or {}).get("hugli"))
    coastal = hugli and coast_km is not None and float(coast_km) <= 40
    rain3 = sum(h["mm"] for h in hours[:3])
    phase = (now.hour + now.minute / 60 + (float(lon or 88.5) / 15.0)) % 12.42
    high = phase < 2.2 or phase > 10.2
    drain = bool(coastal and high and rain3 >= 4)
    swell = bool(coastal and wave_m is not None and float(wave_m) >= 1.8 and rain3 >= 2)
    return {
        "relevant": hugli,
        "coastal": coastal,
        "high_tide": high if coastal else False,
        "phase_h": round(phase, 2) if hugli else None,
        "rain_3h_mm": round(rain3, 2),
        "wave_height_m": wave_m,
        "drain_blocked": drain,
        "stay_off_ghat": bool(drain or swell),
        "method": "tide-rain compound v2 (Hugli only)",
        "note": "Hugli harmonic prior only. Hidden off the estuary.",
    }


def pluvial_fluvial(pond: dict[str, Any], f: dict[str, Any], flood_score: int) -> dict[str, Any]:
    pluvial = pond["mm_60"] >= 2.0 or pond["mm_120"] >= 3.5
    rising = str(f.get("discharge_trend") or "") == "rising"
    fluvial = rising or flood_score >= 55
    return {
        "pluvial": pluvial,
        "fluvial": fluvial,
        "field_stands_water": pluvial,
        "river_later": fluvial,
        "discharge_trend": f.get("discharge_trend") or "steady",
        "flood_score": flood_score,
        "method": "pluvial vs fluvial split v1",
        "note": "0–6 h ponding is not GloFAS. River card is a later-day watch.",
    }


def pump_regret(hours: list[dict[str, Any]], plot_m2: float, hy: dict[str, Any], p_delta: float = 0.0) -> dict[str, Any]:
    rain90 = sum(h["mm"] for h in hours[:2])
    p_wet = float(hours[0]["p_wet"]) if hours and hours[0].get("p_wet") is not None else _clip(rain90 / 6.0, 0.0, 0.95)
    p_mm = _clip(rain90 / 5.0, 0.0, 0.95)
    p = _clip(0.35 * p_wet + 0.65 * p_mm + p_delta, 0.0, 0.95)
    if hours[:2] and hours[0]["mm"] >= 1.2:
        p = max(p, 0.55)
    mid = plot_m2 * 2.5
    wasted = int(round(mid * p * (0.7 + 0.3 * float(hy.get("memory") or 0.4))))
    hold = p >= 0.45 and rain90 >= 0.8
    return {
        "p_interrupt_90m": round(p, 3),
        "set_min": 90,
        "liters_at_risk": wasted,
        "rain_90m_mm": round(rain90, 2),
        "action": "hold" if hold else "ok",
        "method": "pump-set decision nowcast v1",
    }


def cost_loss(pump: dict[str, Any], hours: list[dict[str, Any]], ph: dict[str, Any], plot_m2: float) -> dict[str, Any]:
    rain2 = sum(h["mm"] for h in hours[:2])
    stage = float(ph.get("stage_score") or 0.55)
    stress = max(0.0, 4.0 - rain2) * stage
    wasted = int(pump.get("liters_at_risk") or 0)
    prefer = "hold" if pump.get("action") == "hold" or wasted > plot_m2 * 1.2 else "ok"
    return {
        "wasted_liters_if_apply": wasted,
        "stress_mm_if_wait_2h": round(stress, 2),
        "prefer": prefer,
        "method": "90-min cost-loss v1",
    }


def air_hours(f: dict[str, Any]) -> dict[str, Any]:
    times = list(f.get("hourly_aqi_times") or f.get("hourly_times") or [])
    vals = [float(x) for x in (f.get("hourly_us_aqi") or [])]
    if not vals:
        now = f.get("us_aqi") or f.get("naqi")
        return {
            "hours": [],
            "peak_us_aqi": int(now) if now is not None else None,
            "method": "open-meteo air 0–6h (no hourly series)",
        }
    _, future = split_hours(times, vals)
    rows = [{"t": h["t"], "lead_h": i + 1, "us_aqi": int(round(h["mm"]))} for i, h in enumerate(future[:6])]
    peak = max((r["us_aqi"] for r in rows), default=None)
    if not peak:
        now = f.get("us_aqi") if f.get("us_aqi") is not None else f.get("naqi")
        peak = int(now) if now is not None else None
    return {
        "hours": rows,
        "peak_us_aqi": peak,
        "method": "open-meteo air 0–6h (not CPCB nowcast)",
    }


def labour_window(f: dict[str, Any], air: dict[str, Any]) -> dict[str, Any]:
    from app.science.wbgt import estimate

    tmax = (f.get("temp_max") or [30])[0]
    rh = float(f.get("rh_now") or 60)
    peak = air.get("peak_us_aqi")
    if peak is None:
        peak = f.get("naqi") or f.get("us_aqi") or 0
    peak = int(peak or 0)
    wind = f.get("wind_speed_ms") or f.get("wind_now_ms")
    wb = estimate(float(tmax), rh, wind)
    closed = (wb["wbgt_c"] >= 28 and peak >= 151) or (float(tmax) >= 36 and rh >= 55 and peak >= 151)
    return {
        "closed_2h": closed,
        "tmax_c": round(float(tmax), 1),
        "rh": rh,
        "peak_us_aqi": peak,
        "wbgt_c": wb["wbgt_c"],
        "wbgt_level": wb["level"],
        "method": "WBGT×AQI labour window v2",
    }


def squall_vis(st: dict[str, Any], kal: dict[str, Any]) -> dict[str, Any]:
    vis = st.get("visibility_km")
    watch = kal.get("level") == "watch" or (
        float(st.get("wind_shift_deg") or 0) >= 40 and float(st.get("cloud_jump") or 0) >= 15
    )
    if vis is not None and float(vis) < 2:
        watch = True
    return {
        "watch": bool(watch),
        "visibility_km": vis,
        "method": "squall/visibility watch v1",
        "note": "Do not stay on the bund if watch is true.",
    }


def field_access(
    hours: list[dict[str, Any]],
    pond: dict[str, Any],
    clock: dict[str, Any],
    labour: dict[str, Any],
    ph: dict[str, Any],
    squall: dict[str, Any],
    phys: dict[str, Any] | None = None,
) -> dict[str, Any]:
    stage = ph.get("stage") or "unknown"
    kind = (phys or {}).get("kind") or ""
    if stage in {"transplant", "cri", "flowering"}:
        pond_lim = 1.5
        need_dry = False
    elif stage in {"maturity", "grain_fill"}:
        pond_lim = 4.0
        need_dry = True
    else:
        pond_lim = 3.0
        need_dry = False
    if kind == "arid":
        pond_lim *= 3.0
    elif kind == "orographic":
        pond_lim *= 1.6
    reasons: list[str] = []
    if pond["mm_60"] >= pond_lim:
        reasons.append("ponding")
    if kind == "orographic" and hours and hours[0]["mm"] >= 1.2:
        reasons.append("slope-runoff")
    if clock.get("t_start") and hours and hours[0]["lead_h"] <= 2 and hours[0]["mm"] >= 0.8:
        reasons.append("onset")
    if labour.get("closed_2h"):
        reasons.append("heat×AQI")
    if squall.get("watch") and hours and hours[0]["mm"] >= 0.4:
        reasons.append("storm")
    if need_dry:
        dry2 = all(h["mm"] < 0.3 for h in hours[:2]) if hours[:2] else False
        if not dry2:
            reasons.append("harvest-wet")
    blocked = bool(reasons)
    p_closed = 0.78 if blocked else 0.15 if pond["mm_120"] >= 1.5 else 0.05
    return {
        "enterable": not blocked,
        "p_closed_2h": round(p_closed, 3),
        "reasons": reasons or ["open"],
        "stage": stage,
        "method": "phenology-gated 2h field-access v1",
    }


def fuse_speech(speech: str | None, kal: dict[str, Any]) -> dict[str, Any]:
    heard = observe_speech(speech or "")
    tags = set(heard.get("tags") or [])
    onset_pull = bool(tags & {"squall", "heavy_rain", "flood", "waterlog", "river_rise"})
    p_delta = 0.0
    if tags & {"squall", "heavy_rain"}:
        p_delta = 0.12
        kal["score_pct"] = int(min(95, int(kal.get("score_pct") or 0) + 12))
        if kal["score_pct"] >= 55:
            kal["level"] = "watch"
    elif tags & {"flood", "waterlog", "river_rise"}:
        p_delta = 0.08
    return {
        "heard": heard,
        "onset_pull": onset_pull,
        "p_interrupt_delta": p_delta,
        "mm_changed": False,
        "method": "vernacular nowcast fuse v1",
        "note": "Speech updates category and timing only. Millimetres stay on tools.",
    }


def apply_speech_only(pack: dict[str, Any], speech: str) -> dict[str, Any]:
    """Re-apply speech to a built pack. Does not rewrite millimetres."""
    import copy

    out = copy.deepcopy(pack)
    kal = out.get("kal") or {}
    speech_pack = fuse_speech(speech, kal)
    out["kal"] = kal
    out["speech"] = speech_pack
    clock = onset_cessation(out.get("hours") or [], pull=speech_pack["onset_pull"] or (out.get("cap") or {}).get("onset_pull"))
    out["clock"] = clock
    pump = out.get("pump") or {}
    if pump:
        p = _clip(float(pump.get("p_interrupt_90m") or 0) + speech_pack["p_interrupt_delta"], 0, 0.95)
        pump["p_interrupt_90m"] = round(p, 3)
        rain90 = float(pump.get("rain_90m_mm") or 0)
        pump["action"] = "hold" if p >= 0.45 and rain90 >= 0.8 else "ok"
        out["pump"] = pump
    out["actions"] = decide_actions(out)
    out["locked"] = locked(out)
    return out


def error_memory(
    district: str,
    regime_name: str,
    hours: list[dict[str, Any]],
    past: list[dict[str, Any]],
    *,
    write: bool = True,
) -> dict[str, Any]:
    key = f"nowcast:err:{district or 'x'}:{regime_name or 'x'}"
    prev = cache.get(key)
    frac = 0.0
    hit = None
    if isinstance(prev, dict) and past:
        issued = float(prev.get("mm") or 0)
        obs = float(past[-1]["mm"])
        if issued > 0.15 or obs > 0.15:
            hit = round(obs - issued, 2)
            frac = _clip(hit / max(issued, 0.5), -0.2, 0.2)
    if write and hours:
        cache.set(key, {"mm": hours[0]["mm"], "t": hours[0]["t"], "regime": regime_name}, ttl_s=3 * 3600)
    sk_key = f"nowcast:skill:{district or 'x'}"
    raw = cache.get(sk_key)
    log = raw if isinstance(raw, list) else []
    if write and hit is not None:
        log = list(log) + [{"regime": regime_name, "err_mm": hit}]
        log = log[-24:]
        cache.set(sk_key, log, ttl_s=7 * 86400)
    by: dict[str, list[float]] = {}
    for row in log or []:
        by.setdefault(str(row.get("regime") or "x"), []).append(float(row.get("err_mm") or 0))
    skill = {
        k: {"n": len(v), "mae_mm": round(sum(abs(x) for x in v) / len(v), 2)}
        for k, v in by.items()
        if v
    }
    return {
        "last_error_mm": hit,
        "frac": round(frac, 3),
        "by_regime": skill,
        "imd_station_verify": {
            "available": False,
            "note": "IMD REST is unauthorized. Skill is vs the next Open-Meteo hour, not a gauge.",
        },
        "method": "plus-1h error memory v1",
    }


def decide_actions(pack: dict[str, Any]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    pump = pack.get("pump") or {}
    access = pack.get("access") or {}
    kal = pack.get("kal") or {}
    squall = pack.get("squall") or {}
    tide = pack.get("tide") or {}
    cost = pack.get("cost") or {}
    if pump.get("action") == "hold":
        out.append(
            {
                "id": "nowcast_pump_hold",
                "priority": 0,
                "verb": "do_not_start",
                "who": "farmer",
                "when": "next 90 min",
                "action": "Do not start the pump set — rain may interrupt it.",
                "template_id": "nowcast_pump_hold",
                "slots": {
                    "p_interrupt_90m": pump.get("p_interrupt_90m"),
                    "liters_at_risk": pump.get("liters_at_risk"),
                    "rain_90m_mm": pump.get("rain_90m_mm"),
                },
            }
        )
    elif cost.get("prefer") == "ok":
        out.append(
            {
                "id": "nowcast_pump_ok",
                "priority": 3,
                "verb": "ok",
                "who": "farmer",
                "when": "next 90 min",
                "action": "Pump set is unlikely to be interrupted in the next 90 minutes.",
                "template_id": "nowcast_pump_ok",
                "slots": {
                    "p_interrupt_90m": pump.get("p_interrupt_90m"),
                    "stress_mm_if_wait_2h": cost.get("stress_mm_if_wait_2h"),
                },
            }
        )
    if kal.get("level") == "watch" or squall.get("watch"):
        kal_line = (
            "Storm / Kal Baisakhi watch — do not stay on the bund."
            if kal.get("kal_belt")
            else "Storm watch — do not stay in the open."
        )
        out.append(
            {
                "id": "nowcast_take_cover",
                "priority": 0,
                "verb": "take_cover",
                "who": "labour",
                "when": "next 2 h",
                "action": kal_line,
                "template_id": "nowcast_take_cover",
                "slots": {"kal_level": kal.get("level"), "visibility_km": squall.get("visibility_km")},
            }
        )
    if access.get("enterable") is False:
        out.append(
            {
                "id": "nowcast_stay_off",
                "priority": 1,
                "verb": "stay_off",
                "who": "field worker",
                "when": "next 2 h",
                "action": "Field is not enterable for the next two hours.",
                "template_id": "nowcast_stay_off",
                "slots": {
                    "p_closed_2h": access.get("p_closed_2h"),
                    "reasons": access.get("reasons"),
                    "stage": access.get("stage"),
                },
            }
        )
    if tide.get("stay_off_ghat"):
        out.append(
            {
                "id": "nowcast_ghat",
                "priority": 1,
                "verb": "stay_off",
                "who": "boat / ghat",
                "when": "next 3 h",
                "action": "Coastal drain may be blocked — stay off the ghat.",
                "template_id": "nowcast_ghat",
                "slots": {
                    "drain_blocked": tide.get("drain_blocked"),
                    "rain_3h_mm": tide.get("rain_3h_mm"),
                },
            }
        )
    return out


def locked(pack: dict[str, Any]) -> dict[str, Any]:
    hours = pack.get("hours") or []
    pump = pack.get("pump") or {}
    access = pack.get("access") or {}
    clock = pack.get("clock") or {}
    pond = pack.get("ponding") or {}
    kal = pack.get("kal") or {}
    tide = pack.get("tide") or {}
    cost = pack.get("cost") or {}
    air = pack.get("air") or {}
    labour = pack.get("labour") or {}
    split = pack.get("split") or {}
    place = pack.get("place") or {}
    return {
        "hours": [
            {"t": h["t"], "lead_h": h["lead_h"], "mm": h["mm"], "p_wet": h.get("p_wet"), "engine": h["engine"]}
            for h in hours
        ],
        "onset": clock.get("t_start"),
        "cessation": clock.get("t_stop"),
        "ponding_60_mm": pond.get("mm_60"),
        "ponding_120_mm": pond.get("mm_120"),
        "p_interrupt_90m": pump.get("p_interrupt_90m"),
        "liters_at_risk": pump.get("liters_at_risk"),
        "wasted_liters_if_apply": cost.get("wasted_liters_if_apply"),
        "stress_mm_if_wait_2h": cost.get("stress_mm_if_wait_2h"),
        "enterable_2h": access.get("enterable"),
        "p_closed_2h": access.get("p_closed_2h"),
        "regime": (pack.get("regime") or {}).get("name"),
        "kal_level": kal.get("level"),
        "drain_blocked": tide.get("drain_blocked"),
        "pluvial": split.get("pluvial"),
        "fluvial": split.get("fluvial"),
        "peak_us_aqi_6h": air.get("peak_us_aqi"),
        "labour_closed_2h": labour.get("closed_2h"),
        "place_name": place.get("name"),
        "place_kind": place.get("kind"),
        "convective": {
            "lightning": (pack.get("convective") or {}).get("lightning"),
            "cloudburst": (pack.get("convective") or {}).get("cloudburst"),
            "downburst": (pack.get("convective") or {}).get("downburst"),
        },
        "engine_note": "0–2h nowcast, 3–4h blend, 5–6h NWP. Past hours are Open-Meteo model analysis, not a gauge. Do not invent millimetres.",
    }


def build(
    f: dict[str, Any],
    loc: Any,
    *,
    hy: dict[str, Any],
    ph: dict[str, Any] | None = None,
    neighbors: list[dict[str, Any]] | None = None,
    speech: str | None = None,
    plot_m2: float = 400.0,
    cap_hit: bool = False,
    caps: list[dict[str, Any]] | None = None,
    flood_score: int = 0,
    live_sat: dict[str, Any] | None = None,
) -> dict[str, Any]:
    ph = ph or {}
    neighbors = neighbors or []
    times = list(f.get("hourly_times") or [])
    vals = [float(x) for x in (f.get("hourly_precip") or [])]
    past, future = split_hours(times, vals)
    st = state_vector(f)
    lat = getattr(loc, "lat", None)
    phys = classify(lat, getattr(loc, "lon", None), loc=loc, coast_km=f.get("coast_km"))
    reg = regime(past, f, st, lat, phys)
    adv = advection(loc, neighbors)
    pair = stream_pair(loc, neighbors, adv)
    storm = neighbor_storm(neighbors, past)
    hood = neighborhood_skill(neighbors, past)
    err0 = error_memory(getattr(loc, "district", "") or "", reg["name"], [], past, write=False)
    cap = cap_prior(caps, cap_hit)
    probs_future: list[float] = []
    all_prob = [float(x) for x in (f.get("hourly_prob") or [])]
    if all_prob and times:
        _, pf = split_hours(times, all_prob)
        probs_future = [p["mm"] for p in pf[:6]]
    hours = blend_hours(past, future, reg, adv, float(err0.get("frac") or 0), cap, probs_future)
    kal = kal_baisakhi(f, past, st, phys=phys)
    speech_pack = fuse_speech(speech, kal)
    pull = bool(speech_pack["onset_pull"] or cap.get("onset_pull"))
    clock = onset_cessation(hours, pull=pull)
    pond = ponding(hours, hy, phys)
    budget = hourly_budget(hours, hy)
    tide = tide_rain(hours, f.get("coast_km"), getattr(loc, "lon", None), f.get("wave_height_m"), phys=phys)
    split = pluvial_fluvial(pond, f, flood_score)
    pump = pump_regret(hours, plot_m2, hy, p_delta=float(speech_pack.get("p_interrupt_delta") or 0))
    cost = cost_loss(pump, hours, ph, plot_m2)
    air = air_hours(f)
    labour = labour_window(f, air)
    squall = squall_vis(st, kal)
    access = field_access(hours, pond, clock, labour, ph, squall, phys)
    err = error_memory(getattr(loc, "district", "") or "", reg["name"], hours, past)
    place = {
        "kind": getattr(loc, "place_kind", None) or "district",
        "name": getattr(loc, "place_name", None) or getattr(loc, "district", None),
        "district": getattr(loc, "district", None),
        "lat": getattr(loc, "lat", None),
        "lon": getattr(loc, "lon", None),
        "note": "Nowcast is for the resolved gazetteer point, not a district mean.",
    }
    obs_tail = [
        {"t": p["t"], "mm": p["mm"], "engine": "observed", "source": "open-meteo-analysis"}
        for p in past[-16:]
    ]
    pack = {
        "regime": reg,
        "state": st,
        "advection": adv,
        "stream": pair,
        "neighbor_storm": storm,
        "neighborhood": hood,
        "cap": cap,
        "hours": hours,
        "observed": obs_tail,
        "clock": clock,
        "ponding": pond,
        "budget": budget,
        "pump": pump,
        "cost": cost,
        "access": access,
        "kal": kal,
        "tide": tide,
        "split": split,
        "air": air,
        "labour": labour,
        "squall": squall,
        "speech": speech_pack,
        "error": err,
        "place": place,
        "phys": phys,
        "method": "decision nowcast angles A–H v2",
    }
    from app.science.convective import build as build_conv
    from app.science.sat_live import compact as compact_sat

    pack["sat_live"] = compact_sat(live_sat)
    pack["convective"] = build_conv(f, loc, live=live_sat, phys=phys)
    pack["actions"] = decide_actions(pack)
    pack["locked"] = locked(pack)
    from app.science.live import attach_live, persist_issue
    from app.science.sat_kalman import attach_to_nowcast

    attach_live(pack, loc)
    attach_to_nowcast(pack, loc, f)
    persist_issue(f"{getattr(loc, 'district', '')}:{getattr(loc, 'place_name', '')}", pack)
    return pack


async def fetch_neighbors(loc: Any, limit: int = 3) -> list[dict[str, Any]]:
    """Cached Open-Meteo hours on nearby gazetteer points."""
    import asyncio

    from app.ml.features import extract
    from app.providers import open_meteo
    from app.services.location_svc import nearby

    lat = float(getattr(loc, "lat", 0) or 0)
    lon = float(getattr(loc, "lon", 0) or 0)
    key = f"nowcast:nb:{round(lat, 3)}:{round(lon, 3)}:{limit}"
    hit = cache.get(key)
    if isinstance(hit, list):
        return hit
    rows = nearby(lat, lon, limit=max(limit, 8))

    async def one(n: Any) -> dict[str, Any] | None:
        try:
            om = await open_meteo.forecast(n.lat, n.lon)
            feat = extract(om, {}, [], None, None)
            return {
                "id": n.id,
                "district": n.district,
                "lat": n.lat,
                "lon": n.lon,
                "hourly_precip": feat.get("hourly_precip") or [],
                "hourly_times": feat.get("hourly_times") or [],
            }
        except Exception:
            return None

    got = await asyncio.gather(*[one(n) for n in rows])
    out = [g for g in got if g]
    cache.set(key, out, 90)
    return out

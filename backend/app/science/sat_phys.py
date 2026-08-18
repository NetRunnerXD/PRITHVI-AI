"""Sub-hourly rain-rate shape between observation scenes.

Hourly analysis is a knot, not a bar. Intra-hour structure comes from
published convective-cell lifetimes (Byers–Braham ~20–40 min, faster rise
than decay), Lagrangian advection of upstream rain, CAPE / moisture /
cloud-layer efficiency, weather-code class, and the Bengal diurnal cycle.

Does not invent locked hourly millimetres. Pulses are deterministic given
the driver knots (no per-refresh noise).
"""

from __future__ import annotations

import math
from datetime import datetime, timedelta
from typing import Any

from app.science.live import _hermite, _pchip_slopes
from app.science.nowcast import IST, _clip, _parse

# Weather-code → (class, amplitude, lifetime_s, n_pulses)
_CODE = (
    (95, "thunder", 1.65, 16 * 60, 2),
    (80, "shower", 1.25, 20 * 60, 2),
    (65, "heavy", 1.05, 28 * 60, 1),
    (61, "rain", 0.75, 34 * 60, 1),
    (51, "drizzle", 0.35, 40 * 60, 1),
    (45, "fog", 0.08, 50 * 60, 0),
)


def code_class(code: float | int | None, precip_mm: float = 0.0) -> tuple[str, float, float, int]:
    if code is not None:
        c = int(code)
        for thresh, name, amp, life, n in _CODE:
            if c >= thresh:
                return name, amp, float(life), n
    if precip_mm >= 4:
        return "cell", 1.4, 18 * 60.0, 2
    if precip_mm >= 1.2:
        return "shower", 1.1, 22 * 60.0, 2
    if precip_mm >= 0.35:
        return "rain", 0.7, 32 * 60.0, 1
    return "dry", 0.06, 40 * 60.0, 0


def _f(v: Any, default: float = 0.0) -> float:
    try:
        if v is None:
            return default
        return float(v)
    except (TypeError, ValueError):
        return default


def _series(f: dict[str, Any], key: str) -> list[float | None]:
    raw = f.get(key) or []
    out: list[float | None] = []
    for x in raw:
        try:
            out.append(None if x is None else float(x))
        except (TypeError, ValueError):
            out.append(None)
    return out


def _fill(vals: list[float | None]) -> list[float]:
    if not vals:
        return []
    last = 0.0
    for v in vals:
        if v is not None:
            last = v
            break
    out: list[float] = []
    for v in vals:
        if v is None:
            out.append(last)
        else:
            last = v
            out.append(v)
    return out


def drivers_from_features(f: dict[str, Any], loc: Any, pack: dict[str, Any] | None = None) -> dict[str, Any]:
    pack = pack or {}
    times_raw = list(f.get("hourly_times") or [])
    times: list[str] = []
    dts: list[datetime] = []
    for t in times_raw:
        dt = _parse(str(t))
        if dt is None:
            continue
        times.append(str(t))
        dts.append(dt)
    n = len(dts)
    adv = pack.get("advection") or {}
    stream = pack.get("stream") or {}
    kal = pack.get("kal") or {}
    storm = pack.get("neighbor_storm") or {}
    coast = f.get("coast_km")
    return {
        "times": times,
        "precip": _fill(_series(f, "hourly_precip"))[:n],
        "cloud": _fill(_series(f, "hourly_cloud"))[:n],
        "cloud_low": _fill(_series(f, "hourly_cloud_low") or _series(f, "hourly_cloud"))[:n],
        "rh": _fill(_series(f, "hourly_rh"))[:n],
        "temp": _fill(_series(f, "hourly_temp"))[:n],
        "dew": _fill(_series(f, "hourly_dew") or _series(f, "hourly_temp"))[:n],
        "cape": _fill(_series(f, "hourly_cape"))[:n],
        "pressure": _fill(_series(f, "hourly_pressure"))[:n],
        "gust": _fill(_series(f, "hourly_gust") or _series(f, "hourly_wind"))[:n],
        "wind": _fill(_series(f, "hourly_wind"))[:n],
        "vpd": _fill(_series(f, "hourly_vpd"))[:n],
        "code": _fill(_series(f, "hourly_weather_code"))[:n],
        "prob": _fill(_series(f, "hourly_prob"))[:n],
        "soil": _fill(_series(f, "hourly_soil"))[:n],
        "lat": float(getattr(loc, "lat", 0) or 0),
        "lon": float(getattr(loc, "lon", 0) or 0),
        "coast_km": None if coast is None else float(coast),
        "regime": str((pack.get("regime") or {}).get("name") or ""),
        "eta_h": stream.get("eta_h"),
        "upstream_mm": adv.get("upstream_mm"),
        "speed_kmh": _f(adv.get("speed_kmh")),
        "kal_watch": kal.get("level") == "watch",
        "wet_neighbors": int(storm.get("wet_neighbors") or 0),
        "dts": dts,
    }


def compact_drivers(drv: dict[str, Any]) -> dict[str, Any]:
    """JSON-safe slice the client / later pack() can hydrate."""
    skip = {"dts", "_pulses"}
    out: dict[str, Any] = {}
    for k, v in drv.items():
        if k in skip:
            continue
        out[k] = v
    return out


def hydrate(blob: dict[str, Any] | None) -> dict[str, Any] | None:
    if not blob or not blob.get("times"):
        return None
    dts = []
    for t in blob["times"]:
        dt = _parse(str(t))
        if dt:
            dts.append(dt)
    out = dict(blob)
    out["dts"] = dts
    return out if dts else None


def _interp(dts: list[datetime], vals: list[float], t: datetime) -> float:
    if not dts or not vals:
        return 0.0
    n = min(len(dts), len(vals))
    dts, vals = dts[:n], vals[:n]
    if n == 1 or t <= dts[0]:
        return float(vals[0])
    if t >= dts[-1]:
        return float(vals[-1])
    xs = [(d - dts[0]).total_seconds() / 3600.0 for d in dts]
    x = (t - dts[0]).total_seconds() / 3600.0
    sl = _pchip_slopes(xs, vals)
    for i in range(n - 1):
        if xs[i] <= x <= xs[i + 1]:
            return max(0.0, _hermite(xs[i], xs[i + 1], vals[i], vals[i + 1], sl[i], sl[i + 1], x))
    return float(vals[-1])


def _nearest_code(drv: dict[str, Any], t: datetime) -> float:
    dts = drv.get("dts") or []
    codes = drv.get("code") or []
    if not dts:
        return 0.0
    best = 0
    best_d = None
    for i, d in enumerate(dts):
        dd = abs((t - d).total_seconds())
        if best_d is None or dd < best_d:
            best, best_d = i, dd
    if best < len(codes):
        return _f(codes[best])
    return 0.0


def _nearest_precip(drv: dict[str, Any], t: datetime) -> float:
    dts = drv.get("dts") or []
    precip = drv.get("precip") or []
    if not dts:
        return 0.0
    best = 0
    best_d = None
    for i, d in enumerate(dts):
        dd = abs((t - d).total_seconds())
        if best_d is None or dd < best_d:
            best, best_d = i, dd
    if best < len(precip):
        return _f(precip[best])
    return 0.0


def diurnal(t: datetime, lat: float, coast_km: float | None) -> float:
    """Land: afternoon peak (Dai 2001). Coast: extra weak nocturnal peak."""
    local = t.astimezone(IST) if t.tzinfo else t.replace(tzinfo=IST)
    h = local.hour + local.minute / 60.0 + local.second / 3600.0
    aft = math.sin(math.pi * _clip((h - 8.0) / 10.0, 0.0, 1.0)) ** 2
    coastal = coast_km is not None and float(coast_km) <= 40
    night = 0.0
    if coastal:
        hn = (h + 2.0) % 24.0
        night = math.sin(math.pi * _clip(hn / 8.0, 0.0, 1.0)) ** 2
    mix = 0.72 * aft + 0.28 * night if coastal else aft
    return 0.38 + 0.62 * mix


def _skewed(dt_s: float, sigma: float) -> float:
    """Faster rise, slower decay — Byers–Braham cell hyetograph."""
    s = 0.62 * sigma if dt_s < 0 else 1.28 * sigma
    if s <= 1:
        return 0.0
    return math.exp(-0.5 * (dt_s / s) ** 2)


def schedule_pulses(drv: dict[str, Any]) -> list[dict[str, Any]]:
    dts: list[datetime] = list(drv.get("dts") or [])
    precip = drv.get("precip") or []
    cloud = drv.get("cloud") or []
    cape = drv.get("cape") or []
    codes = drv.get("code") or []
    gust = drv.get("gust") or []
    wind = drv.get("wind") or []
    eta_h = drv.get("eta_h")
    kal_watch = bool(drv.get("kal_watch"))
    wet_n = int(drv.get("wet_neighbors") or 0)
    out: list[dict[str, Any]] = []
    for i, t0 in enumerate(dts):
        p = _f(precip[i]) if i < len(precip) else 0.0
        c = _f(codes[i]) if i < len(codes) else None
        name, amp0, life, n = code_class(c, p)
        ca = _f(cape[i]) if i < len(cape) else 0.0
        if n <= 0 and p < 0.08 and ca < 180:
            continue
        amp = amp0 * max(p, 0.12 * ca / 900.0)
        if kal_watch:
            amp *= 1.18
        if wet_n >= 2:
            amp *= 1.1
        sigma = life / 2.45
        dcloud = 0.0
        if i > 0 and i < len(cloud) and i - 1 < len(cloud):
            dcloud = _f(cloud[i]) - _f(cloud[i - 1])
        if dcloud >= 10:
            base = 12 * 60
        elif dcloud <= -10:
            base = 7 * 60
        else:
            base = 24 * 60
        if eta_h is not None:
            try:
                base = int(abs(float(eta_h) * 3600.0) % 3000)
            except (TypeError, ValueError):
                pass
        hour = t0.hour + t0.minute / 60.0
        if 13.0 <= hour <= 17.0:
            base = int(0.55 * base + 0.45 * 26 * 60)
        gex = 0.0
        if i < len(gust) and i < len(wind):
            gex = max(0.0, _f(gust[i]) - _f(wind[i]))
        n_use = n if n > 0 else (1 if p >= 0.2 or ca >= 400 else 0)
        if gex >= 14:
            n_use = max(n_use, 1)
            amp *= 1.12
        for k in range(n_use):
            center = t0 + timedelta(seconds=base + k * int(life * 0.82))
            out.append(
                {
                    "c": center.astimezone(IST).isoformat(timespec="seconds"),
                    "s": round(sigma * (1.0 - 0.12 * k), 1),
                    "a": round(amp * (1.0 - 0.22 * k), 3),
                    "kind": name,
                }
            )
    return out


def pulse_at(t: datetime, pulses: list[dict[str, Any]]) -> float:
    acc = 0.0
    for p in pulses:
        c = _parse(str(p.get("c") or ""))
        if c is None:
            continue
        acc += _f(p.get("a")) * _skewed((t - c).total_seconds(), max(60.0, _f(p.get("s"), 900)))
    return acc


def advect_at(t: datetime, drv: dict[str, Any]) -> float:
    up = drv.get("upstream_mm")
    eta_h = drv.get("eta_h")
    if up is None or eta_h is None:
        return 0.0
    try:
        up_f = max(0.0, float(up))
        eta_s = float(eta_h) * 3600.0
    except (TypeError, ValueError):
        return 0.0
    if up_f < 0.15:
        return 0.0
    dts = drv.get("dts") or []
    origin = dts[0] if dts else t
    # Recurring crossing phase so history hours also get a traveling bump.
    phase = eta_s % 3300.0
    hour0 = t.replace(minute=0, second=0, microsecond=0)
    center = hour0 + timedelta(seconds=phase)
    tau = 14 * 60.0
    return up_f * 0.85 * _skewed((t - center).total_seconds(), tau)


def r_phys(t: datetime, drv: dict[str, Any], pulses: list[dict[str, Any]] | None = None) -> dict[str, float]:
    """Instantaneous physical rain-rate (mm/h) and its parts."""
    dts = drv.get("dts") or []
    env = _interp(dts, drv.get("precip") or [], t) if dts else 0.0
    cloud = _interp(dts, drv.get("cloud") or [], t) if dts else 0.0
    low = _interp(dts, drv.get("cloud_low") or drv.get("cloud") or [], t) if dts else cloud
    rh = _interp(dts, drv.get("rh") or [], t) if dts else 70.0
    temp = _interp(dts, drv.get("temp") or [], t) if dts else 28.0
    dew = _interp(dts, drv.get("dew") or [], t) if dts else temp - 4.0
    cape = _interp(dts, drv.get("cape") or [], t) if dts else 0.0
    vpd = _interp(dts, drv.get("vpd") or [], t) if dts else 0.0
    press = drv.get("pressure") or []
    dP = 0.0
    if dts and len(press) >= 2:
        dP = _interp(dts, press, t) - _interp(dts, press, t - timedelta(seconds=1800))
    soil = _interp(dts, drv.get("soil") or [], t) if dts else 0.3
    pulses = pulses if pulses is not None else schedule_pulses(drv)
    pu = pulse_at(t, pulses)
    adv = advect_at(t, drv)
    dep = max(0.0, temp - dew)
    moist = 1.0 / (1.0 + math.exp(-(rh - 72.0) / 8.0))
    moist *= 1.0 / (1.0 + max(0.0, vpd) / 0.85)
    moist *= 1.0 / (1.0 + math.exp((dep - 4.2) / 1.4))
    instab = _clip(cape / 1100.0, 0.0, 2.0)
    cloud_w = (max(0.0, cloud) / 100.0) ** 1.25
    low_w = (max(0.0, low) / 100.0) ** 1.1
    dia = diurnal(t, _f(drv.get("lat")), drv.get("coast_km"))
    fall_p = 1.0 / (1.0 + math.exp(dP / 1.2))  # falling pressure → ~1
    soil_w = 1.0 + 0.12 * _clip((soil - 0.28) / 0.2, -0.5, 1.0)
    mod = _clip(
        0.62 + 0.22 * moist * cloud_w + 0.12 * instab * dia + 0.08 * low_w + 0.06 * fall_p,
        0.45,
        1.85,
    )
    bg = env * mod * soil_w
    kind, _, _, _ = code_class(_nearest_code(drv, t), _nearest_precip(drv, t))
    if kind == "dry" and env < 0.05 and pu < 0.05:
        total = max(0.0, 0.35 * bg + 0.1 * adv)
    else:
        total = max(0.0, 0.48 * bg + 0.38 * pu + 0.14 * adv)
    return {
        "r": round(total, 4),
        "env": round(env, 4),
        "mod": round(mod, 4),
        "pulse": round(pu, 4),
        "adv": round(adv, 4),
        "diurnal": round(dia, 4),
    }


def blend(env_mm_h: float, phys: dict[str, float]) -> float:
    """Kalman envelope rides the physical shape; never negative."""
    return max(0.0, float(env_mm_h) * float(phys.get("mod") or 1.0) + 0.72 * float(phys.get("pulse") or 0) + 0.55 * float(phys.get("adv") or 0))

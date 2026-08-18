"""Online Kalman rain-rate between observation scenes.

No public satellite product delivers rainfall at 1 Hz. INSAT-3D/3DR HEM/IMR
are ~30 min (rapid-scan imagery ~4.5 min; QPE still half-hourly). GPM IMERG
Early is 30 min with ~4 h latency. This filter *predicts* every 1 s (or 60 s)
between those knots, then updates on the innovation y = obs − pred when the
next scene arrives.

State x = [ln(r+ε), bias mm/h, decay /hour]. Process: exponential decay of
rate plus a random-walk bias. Observation: scene rain rate ≈ exp(x0)−ε + bias.

Does not rewrite locked hourly millimetres. Open-Meteo hours are
model-analysis, not INSAT/IMERG, unless a satellite adapter is ready.
"""

from __future__ import annotations

import json
import math
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from app.config import ROOT
from app.science.nowcast import IST, _clip, _now, _parse

EPS = 0.05
STATE_PATH = Path(ROOT) / ".cache" / "sat_kalman.json"

# Process-noise densities per hour on [log_rate, bias, decay]
Q_DIAG = (0.08, 0.05, 0.002)
R_OBS = 0.35
MAX_INNOV = 24


def set_state_path(path: Path | str) -> None:
    """Tests point persistence at a temp file."""
    global STATE_PATH
    STATE_PATH = Path(path)


def _empty() -> dict[str, Any]:
    return {
        "x": [math.log(EPS), 0.0, 0.45],
        "P": [[0.8, 0.0, 0.0], [0.0, 0.4, 0.0], [0.0, 0.0, 0.05]],
        "n": 0,
        "mae": 0.0,
        "last_y": None,
        "last_obs_t": None,
        "last_obs_mm_h": None,
        "last_pred_mm_h": None,
        "source": "om-analysis",
        "source_kind": "model-analysis",
        "innovations": [],
        "K": None,
    }


def _load_all() -> dict[str, Any]:
    if not STATE_PATH.exists():
        return {}
    try:
        return json.loads(STATE_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def _save_all(blob: dict[str, Any]) -> None:
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATE_PATH.write_text(json.dumps(blob, ensure_ascii=False), encoding="utf-8")


def place_key(loc: Any) -> str:
    name = getattr(loc, "place_name", None) or getattr(loc, "district", None) or "x"
    lat = round(float(getattr(loc, "lat", 0) or 0), 3)
    lon = round(float(getattr(loc, "lon", 0) or 0), 3)
    return f"{name}:{lat}:{lon}"


def load(key: str) -> dict[str, Any]:
    return {**_empty(), **(_load_all().get(key) or {})}


def save(key: str, st: dict[str, Any]) -> None:
    blob = _load_all()
    blob[key] = st
    _save_all(blob)


def rate_from_x(x: list[float]) -> float:
    r = math.exp(float(x[0])) - EPS
    return max(0.0, r + float(x[1]))


def _envelope(st: dict[str, Any], dt_s: float, adv_mm_h: float = 0.0) -> float:
    x = list(st["x"])
    lam = _clip(float(x[2]), 0.05, 2.5)
    hours = max(0.0, dt_s) / 3600.0
    r0 = max(0.0, math.exp(float(x[0])) - EPS)
    return max(0.0, r0 * math.exp(-lam * hours) + float(x[1]) + 0.15 * float(adv_mm_h))


def _pulses_of(drivers: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not drivers:
        return []
    cached = drivers.get("_pulses")
    if isinstance(cached, list):
        return cached
    from app.science.sat_phys import schedule_pulses

    pulses = schedule_pulses(drivers)
    drivers["_pulses"] = pulses
    return pulses


def predict_rate(
    st: dict[str, Any],
    dt_s: float,
    adv_mm_h: float = 0.0,
    *,
    at: datetime | None = None,
    drivers: dict[str, Any] | None = None,
) -> float:
    """Envelope from Kalman; intra-hour curve from physical drivers when present."""
    env = _envelope(st, dt_s, adv_mm_h)
    if drivers is None or at is None:
        return env
    from app.science.sat_phys import blend, r_phys

    return max(0.0, blend(env, r_phys(at, drivers, _pulses_of(drivers))))


def formula(st: dict[str, Any], adv_mm_h: float = 0.0, drivers: dict[str, Any] | None = None) -> dict[str, Any]:
    """Constants the client needs to tick the same rate at 1 Hz."""
    return {
        "kind": "decay_bias_v1",
        "eps": EPS,
        "adv_mm_h": round(float(adv_mm_h), 4),
        "x": [round(float(v), 5) for v in st["x"]],
        "last_obs_t": st.get("last_obs_t"),
        "last_obs_mm_h": st.get("last_obs_mm_h"),
    }


def _matmul(a: list[list[float]], b: list[list[float]]) -> list[list[float]]:
    n, m, p = len(a), len(b[0]), len(b)
    out = [[0.0] * m for _ in range(n)]
    for i in range(n):
        for j in range(m):
            out[i][j] = sum(a[i][k] * b[k][j] for k in range(p))
    return out


def _add(a: list[list[float]], b: list[list[float]]) -> list[list[float]]:
    return [[a[i][j] + b[i][j] for j in range(len(a[0]))] for i in range(len(a))]


def _T(a: list[list[float]]) -> list[list[float]]:
    return [[a[j][i] for j in range(len(a))] for i in range(len(a[0]))]


def propagate(st: dict[str, Any], dt_s: float) -> dict[str, Any]:
    """EKF time update: decay log-rate, inflate P by Q · hours."""
    hours = max(0.0, dt_s) / 3600.0
    x = [float(v) for v in st["x"]]
    P = [row[:] for row in st["P"]]
    if hours <= 0:
        return {**st, "x": x, "P": P}
    lam = _clip(x[2], 0.05, 2.5)
    r = max(0.0, math.exp(x[0]) - EPS)
    decay = math.exp(-lam * hours)
    r2 = r * decay
    denom = r2 + EPS
    x2 = [math.log(denom), x[1], lam]
    f00 = math.exp(x[0]) * decay / denom
    f02 = -r * hours * decay / denom
    f = [[f00, 0.0, f02], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]]
    q = [[0.0] * 3 for _ in range(3)]
    for i, qi in enumerate(Q_DIAG):
        q[i][i] = qi * max(hours, 1e-3)
    pp = _add(_matmul(_matmul(f, P), _T(f)), q)
    out = dict(st)
    out["x"] = x2
    out["P"] = pp
    return out


def update(
    st: dict[str, Any],
    obs_mm_h: float,
    pred_mm_h: float,
    obs_t: str,
    source: str,
    source_kind: str,
) -> dict[str, Any]:
    """Measurement update on rain-rate. Innovation y = obs − pred."""
    y = float(obs_mm_h) - float(pred_mm_h)
    x = [float(v) for v in st["x"]]
    p = [row[:] for row in st["P"]]
    r0 = max(0.0, math.exp(x[0]) - EPS)
    h = [r0 + EPS, 1.0, 0.0]
    s = sum(h[i] * sum(p[i][j] * h[j] for j in range(3)) for i in range(3)) + R_OBS
    k = [sum(p[i][j] * h[j] for j in range(3)) / s for i in range(3)]
    x2 = [x[i] + k[i] * y for i in range(3)]
    x2[2] = _clip(x2[2], 0.05, 2.5)
    kh = [[k[i] * h[j] for j in range(3)] for i in range(3)]
    ikh = [[(1.0 if i == j else 0.0) - kh[i][j] for j in range(3)] for i in range(3)]
    p2 = _matmul(ikh, p)
    n = int(st.get("n") or 0) + 1
    mae = (float(st.get("mae") or 0) * (n - 1) + abs(y)) / n
    hist = list(st.get("innovations") or [])
    hist.append(
        {
            "t": obs_t,
            "y": round(y, 3),
            "obs": round(float(obs_mm_h), 3),
            "pred": round(float(pred_mm_h), 3),
        }
    )
    return {
        "x": [round(v, 5) for v in x2],
        "P": [[round(v, 5) for v in row] for row in p2],
        "n": n,
        "mae": round(mae, 3),
        "last_y": round(y, 3),
        "last_obs_t": obs_t,
        "last_obs_mm_h": round(float(obs_mm_h), 3),
        "last_pred_mm_h": round(float(pred_mm_h), 3),
        "source": source,
        "source_kind": source_kind,
        "K": [round(v, 4) for v in k],
        "innovations": hist[-MAX_INNOV:],
    }


def ingest_knots(
    key: str,
    knots: list[dict[str, Any]],
    *,
    source: str,
    source_kind: str,
    adv_mm_h: float = 0.0,
    reset: bool = False,
    persist: bool = True,
    drivers: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Walk past observation knots. Update only when a *new* time appears."""
    st = _empty() if reset else load(key)
    last_t = _parse(str(st.get("last_obs_t") or ""))
    for knot in knots:
        dt = _parse(str(knot.get("t") or ""))
        if dt is None:
            continue
        raw = knot.get("mm_h")
        if raw is None:
            raw = knot.get("mm")
        try:
            mm = max(0.0, float(raw))
        except (TypeError, ValueError):
            continue
        if last_t is not None and dt <= last_t:
            continue
        dt_s = (dt - last_t).total_seconds() if last_t else 0.0
        prior = propagate(st, dt_s) if last_t else st
        pred = predict_rate(prior, dt_s, adv_mm_h, at=dt, drivers=drivers)
        st = update(prior, mm, pred, knot["t"], source, source_kind)
        last_t = dt
    if persist:
        save(key, st)
    return st


def series(
    st: dict[str, Any],
    *,
    t0: datetime,
    horizon_s: int,
    stride_s: int,
    origin: datetime | None = None,
    adv_mm_h: float = 0.0,
    drivers: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    stride = max(1, int(stride_s))
    origin = origin or t0
    out: list[dict[str, Any]] = []
    span = max(stride, int(horizon_s))
    for s in range(0, span + 1, stride):
        t = t0 + timedelta(seconds=s)
        dt_s = (t - origin).total_seconds()
        r = predict_rate(st, dt_s, adv_mm_h, at=t, drivers=drivers) if dt_s >= 0 else 0.0
        out.append(
            {
                "t": t.astimezone(IST).isoformat(timespec="seconds"),
                "mm_h": round(r, 3),
                "mm": round(r * stride / 3600.0, 5),
                "engine": "sat_kalman",
                "lead_s": s,
            }
        )
    return out


def _knot_mm(knot: dict[str, Any]) -> float | None:
    raw = knot.get("mm_h")
    if raw is None:
        raw = knot.get("mm")
    try:
        return max(0.0, float(raw))
    except (TypeError, ValueError):
        return None


def replay_history(
    knots: list[dict[str, Any]],
    *,
    source: str = "om-analysis",
    source_kind: str = "model-analysis",
    stride_s: int = 60,
    adv_mm_h: float = 0.0,
    max_knots: int = 16,
    drivers: dict[str, Any] | None = None,
    include_series: bool = True,
) -> dict[str, Any]:
    """Causal walk of past scenes. Predicted path never sees the next obs.

    Truth exists only at scene times. `held` is the last scene held forward —
    a reference, not rain between knots.
    """
    parsed: list[tuple[datetime, str, float]] = []
    for knot in knots:
        dt = _parse(str(knot.get("t") or ""))
        mm = _knot_mm(knot)
        if dt is None or mm is None:
            continue
        parsed.append((dt, str(knot["t"]), mm))
    parsed.sort(key=lambda r: r[0])
    parsed = parsed[-max_knots:]
    stride = max(15, int(stride_s))
    st = _empty()
    last_t: datetime | None = None
    held = 0.0
    series_out: list[dict[str, Any]] = []
    scenes: list[dict[str, Any]] = []

    def _row(
        t: datetime,
        pred: float | None,
        *,
        obs: float | None = None,
        y: float | None = None,
        after: float | None = None,
        scene: bool = False,
    ) -> dict[str, Any]:
        return {
            "t": t.astimezone(IST).isoformat(timespec="seconds"),
            "pred": None if pred is None else round(pred, 3),
            "held": round(held, 3),
            "obs": None if obs is None else round(obs, 3),
            "y": None if y is None else round(y, 3),
            "after": None if after is None else round(after, 3),
            "scene": scene,
        }

    for dt, t_str, mm in parsed:
        if last_t is None:
            pred = predict_rate(st, 0.0, adv_mm_h, at=dt, drivers=drivers)
            y = mm - pred
            scenes.append(
                {
                    "t": t_str,
                    "obs": round(mm, 3),
                    "pred": round(pred, 3),
                    "y": round(y, 3),
                    "after": None,
                }
            )
            st = update(st, mm, pred, t_str, source, source_kind)
            after = rate_from_x(st["x"])
            scenes[-1]["after"] = round(after, 3)
            if include_series:
                series_out.append(_row(dt, pred, obs=mm, y=y, after=after, scene=True))
                series_out.append(_row(dt, None, after=after))
            held = mm
            last_t = dt
            continue

        dt_s = (dt - last_t).total_seconds()
        if dt_s <= 0:
            continue
        s = 0
        while s < dt_s:
            t = last_t + timedelta(seconds=s)
            if include_series:
                series_out.append(_row(t, predict_rate(st, float(s), adv_mm_h, at=t, drivers=drivers)))
            s += stride
        pred = predict_rate(st, dt_s, adv_mm_h, at=dt, drivers=drivers)
        y = mm - pred
        scenes.append(
            {
                "t": t_str,
                "obs": round(mm, 3),
                "pred": round(pred, 3),
                "y": round(y, 3),
                "after": None,
            }
        )
        prior = propagate(st, dt_s)
        st = update(prior, mm, pred, t_str, source, source_kind)
        after = rate_from_x(st["x"])
        scenes[-1]["after"] = round(after, 3)
        if include_series:
            series_out.append(_row(dt, pred, obs=mm, y=y, after=after, scene=True))
            series_out.append(_row(dt, None, after=after))
        held = mm
        last_t = dt

    mae = None
    if scenes:
        mae = round(sum(abs(float(s["y"])) for s in scenes) / len(scenes), 3)
    return {
        "series": series_out,
        "scenes": scenes,
        "mae": mae,
        "n": len(scenes),
        "stride_s": stride,
        "engine": "sat_kalman",
        "note": (
            "Causal replay: the predicted line in each gap is what the filter said "
            "before the next scene. Dots are scene actuals. Offset y = obs − pred. "
            "The dashed hold is the last scene, not rain between knots."
        ),
    }


def integral_mm(st: dict[str, Any], duration_s: int, stride_s: int, adv_mm_h: float = 0.0) -> float:
    """Left-Riemann integral of predicted rate over duration_s (for tests)."""
    t0 = datetime(2026, 1, 1, tzinfo=IST)
    rows = series(st, t0=t0, horizon_s=duration_s, stride_s=stride_s, origin=t0, adv_mm_h=adv_mm_h)
    return sum(float(p["mm"]) for p in rows if int(p["lead_s"]) < int(duration_s))


def pack(
    loc: Any,
    obs_knots: list[dict[str, Any]],
    *,
    source: str,
    source_kind: str,
    stride_s: int = 1,
    adv_mm_h: float = 0.0,
    now: datetime | None = None,
    compact: bool = False,
    persist: bool = True,
    reset: bool = False,
    drivers: dict[str, Any] | None = None,
) -> dict[str, Any]:
    now = now or _now()
    key = place_key(loc)
    st = ingest_knots(
        key,
        obs_knots,
        source=source,
        source_kind=source_kind,
        adv_mm_h=adv_mm_h,
        reset=reset,
        persist=persist,
        drivers=drivers,
    )
    last = _parse(str(st.get("last_obs_t") or "")) or now
    stride = 1 if int(stride_s) <= 1 else 60
    if stride <= 1:
        t_lo = now - timedelta(seconds=180)
        t0 = last if last > t_lo else t_lo
        if t0 < last:
            t0 = last
        horizon = int((now + timedelta(seconds=180) - t0).total_seconds())
        horizon = max(stride, min(horizon, 400))
    else:
        t0 = last
        horizon = 7200
    pred = [] if compact else series(
        st, t0=t0, horizon_s=horizon, stride_s=stride, origin=last, adv_mm_h=adv_mm_h, drivers=drivers
    )
    step = 1800 if source_kind == "satellite-qpe" else 3600
    nxt = last + timedelta(seconds=step)
    next_eta = max(0, int((nxt - now).total_seconds()))
    note = (
        "Kalman envelope plus a physical intra-hour shape (convective pulses, "
        "advection, CAPE, moisture, cloud, weather code, diurnal). "
        "The series is computed on the server. Does not rewrite locked hourly millimetres."
    )
    if source_kind != "satellite-qpe":
        note += " Observation knots are Open-Meteo analysis, not INSAT/IMERG."
    play_dt = max(0.0, (now - last).total_seconds()) if last else 0.0
    from app.science.sat_phys import compact_drivers

    return {
        "place": key,
        "source": st.get("source") or source,
        "source_kind": st.get("source_kind") or source_kind,
        "obs_knots": obs_knots[-16:],
        "pred_series": pred,
        "history": replay_history(
            obs_knots,
            source=source,
            source_kind=source_kind,
            stride_s=60,
            adv_mm_h=adv_mm_h,
            max_knots=12,
            drivers=drivers,
            include_series=not compact,
        ),
        "playhead_rate": round(predict_rate(st, play_dt, adv_mm_h, at=now, drivers=drivers), 3),
        "last_error_mm_h": st.get("last_y"),
        "mae": st.get("mae"),
        "n_updates": st.get("n"),
        "kalman_gain": st.get("K"),
        "next_obs_eta_s": next_eta,
        "stride_s": stride,
        "engine": "sat_kalman",
        "note": note,
        "method": "phys-pulse EKF v2 (server series)",
        "formula": formula(st, adv_mm_h),
        "drivers": compact_drivers(drivers) if drivers else None,
        "innovations": st.get("innovations") or [],
        "rewrites_locked": False,
    }


def attach_to_nowcast(pack_nc: dict[str, Any], loc: Any, f: dict[str, Any]) -> dict[str, Any]:
    """Compact Kalman card on the nowcast pack. Never mutates hours / locked mm."""
    try:
        from app.providers import sat_obs

        times = list(f.get("hourly_times") or [])
        vals: list[float] = []
        for x in f.get("hourly_precip") or []:
            try:
                vals.append(max(0.0, float(x)))
            except (TypeError, ValueError):
                vals.append(0.0)
        obs = sat_obs.from_open_meteo_hours(times, vals, past_only=True)
        locked_mm = [h.get("mm") for h in (pack_nc.get("hours") or [])]
        from app.science.sat_phys import drivers_from_features

        drv = drivers_from_features(f, loc, pack_nc)
        blob = pack(
            loc,
            obs["knots"],
            source=obs["source"],
            source_kind=obs["source_kind"],
            stride_s=60,
            compact=True,
            drivers=drv,
        )
        blob["locked_mm_ref"] = locked_mm
        pack_nc["sat"] = blob
    except Exception:
        pack_nc["sat"] = {"engine": "sat_kalman", "error": "unavailable", "rewrites_locked": False}
    return pack_nc

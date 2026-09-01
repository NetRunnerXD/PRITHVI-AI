"""EQMN quantile blending, diagnostic mixture PDF, IMD extreme branch, Schaake shuffle."""

from __future__ import annotations

import math
from typing import Any

from app.ml.hybrid_blend import RAIN_EXTREME_MM, RAIN_HEAVY_MM, RAIN_VERY_HEAVY_MM, p_exceed, vincentize

RAIN_VERY_HEAVY_DOC = 115.6
QUANTILES = [0.1, 0.25, 0.5, 0.75, 0.9, 0.95, 0.99]


def pinball_loss(y_true: float, y_pred: float, tau: float) -> float:
    error = float(y_true) - float(y_pred)
    if error >= 0:
        return tau * error
    return (tau - 1.0) * error


def pinball_mean(y_true: list[float], y_pred: list[float], tau: float) -> float | None:
    if not y_true or len(y_true) != len(y_pred):
        return None
    return round(sum(pinball_loss(a, b, tau) for a, b in zip(y_true, y_pred)) / len(y_true), 6)


def member_quantiles(mu: float, sigma: float, p95: float | None = None, p99: float | None = None) -> dict[float, float]:
    """Q(0.5)=member value; tails stretch toward climatology p95/p99, not a Gaussian mixture."""
    mu = float(mu)
    sig = max(float(sigma), 0.4)
    hi95 = float(p95) if p95 is not None else mu + 1.64 * sig
    hi99 = float(p99) if p99 is not None else mu + 2.33 * sig
    lo = max(0.0, mu - 1.28 * sig)
    out: dict[float, float] = {}
    for tau in QUANTILES:
        if tau <= 0.5:
            t = tau / 0.5
            q = lo + t * (mu - lo)
        elif tau <= 0.95:
            t = (tau - 0.5) / 0.45
            q = mu + t * (max(hi95, mu) - mu)
        else:
            t = (tau - 0.95) / 0.04
            q = max(hi95, mu) + t * (max(hi99, hi95, mu) - max(hi95, mu))
        out[tau] = max(0.0, q) if mu >= 0 else q
    return out


def blend_quantiles(model_quantiles: list[dict[float, float]], weights: list[float]) -> dict[float, float]:
    if not model_quantiles:
        return {t: 0.0 for t in QUANTILES}
    wsum = sum(weights) or 1.0
    ws = [w / wsum for w in weights]
    blended: dict[float, float] = {}
    prev = None
    for tau in QUANTILES:
        v = sum(w * float(q.get(tau, 0.0)) for w, q in zip(ws, model_quantiles))
        if prev is not None:
            v = max(v, prev)
        blended[tau] = round(v, 4)
        prev = v
    return blended


def p_from_quantiles(blended: dict[float, float], threshold: float) -> float:
    """P(Y ≥ threshold) from the blended quantile function."""
    items = sorted(blended.items())
    if not items:
        return 0.0
    if threshold <= items[0][1]:
        return 1.0
    if threshold > items[-1][1]:
        return round(max(0.0, 1.0 - items[-1][0]), 4)
    for i in range(1, len(items)):
        t0, q0 = items[i - 1]
        t1, q1 = items[i]
        if q0 <= threshold <= q1:
            if q1 == q0:
                return round(1.0 - t1, 4)
            frac = (threshold - q0) / (q1 - q0)
            tau = t0 + frac * (t1 - t0)
            return round(max(0.0, min(1.0, 1.0 - tau)), 4)
    return 0.0


def gaussian_pdf(xs: list[float], mu: float, sig: float) -> list[float]:
    sig = max(sig, 0.4)
    return [math.exp(-0.5 * ((x - mu) / sig) ** 2) / (sig * math.sqrt(2 * math.pi)) for x in xs]


def mixture_pdf(members: list[tuple[float, float]], weights: list[float], grid: list[float]) -> list[float]:
    dens = [0.0] * len(grid)
    wsum = sum(weights) or 1.0
    for (mu, sig), w in zip(members, weights):
        g = gaussian_pdf(grid, mu, sig)
        ww = w / wsum
        for i, v in enumerate(g):
            dens[i] += ww * v
    return [round(v, 6) for v in dens]


def schaake_shuffle(traces: list[list[float]], historical: list[list[float]]) -> list[list[float]]:
    """Reorder each lead of traces to match historical spatial rank structure."""
    if not traces or not historical:
        return traces
    n = min(len(traces), len(historical))
    if n == 0 or not traces[0] or not historical[0]:
        return traces
    m = min(min(len(t) for t in traces[:n]), min(len(h) for h in historical[:n]))
    if m <= 0:
        return traces
    out = [list(t[:m]) for t in traces[:n]]
    for j in range(m):
        hist_order = sorted(range(n), key=lambda i: historical[i][j])
        fc_sorted = sorted(out[i][j] for i in range(n))
        for rank, i in enumerate(hist_order):
            out[i][j] = fc_sorted[rank]
    return out


def run(
    members: dict[str, dict],
    weights: dict[str, float],
    historical: dict[str, Any],
    day_i: int = 0,
    y_true: float | None = None,
) -> dict[str, Any]:
    ids: list[str] = []
    mus: list[float] = []
    ws: list[float] = []
    for sid, pack in members.items():
        ser = pack.get("precip_days") or []
        if day_i < len(ser) and sid in weights:
            ids.append(sid)
            mus.append(float(ser[day_i]))
            ws.append(float(weights[sid]))
    clim = historical.get("climatology") or {}
    p95 = clim.get("p95")
    p99 = clim.get("p99")
    sigs = [max(2.0, abs(m) * 0.35 + 1.5) for m in mus]
    model_qs = [member_quantiles(m, s, p95, p99) for m, s in zip(mus, sigs)]
    try:
        from app.ml.train.eqrn import predict_quantiles

        trained = []
        for m, s in zip(mus, sigs):
            q = predict_quantiles([m, m, m, 24.0 / 48.0])
            trained.append(q or member_quantiles(m, s, p95, p99))
        if trained and all(trained):
            model_qs = trained
    except Exception:
        pass
    blended = blend_quantiles(model_qs, ws) if mus else {t: 0.0 for t in QUANTILES}
    vin = vincentize(mus, ws) if mus else {"q10": 0, "q50": 0, "q90": 0, "mean": 0, "pop": 0}
    xs = [i * 2.0 for i in range(0, 80)]
    pdf = mixture_pdf(list(zip(mus, sigs)), ws, xs) if mus else []
    ww = ws if ws else None
    heavy_g = p_exceed(mus, RAIN_HEAVY_MM, ww) if mus else 0.0
    vheavy_g = p_exceed(mus, RAIN_VERY_HEAVY_DOC, ww) if mus else 0.0
    extreme_g = p_exceed(mus, RAIN_EXTREME_MM, ww) if mus else 0.0
    heavy = p_from_quantiles(blended, RAIN_HEAVY_MM)
    vheavy = p_from_quantiles(blended, RAIN_VERY_HEAVY_DOC)
    extreme = p_from_quantiles(blended, RAIN_EXTREME_MM)
    traces = []
    for sid in ids:
        ser = [float(x) for x in (members[sid].get("precip_days") or [])[:7]]
        while len(ser) < 7:
            ser.append(ser[-1] if ser else 0.0)
        traces.append(ser)
    hist_mm = float(clim.get("mean") or 6)
    hist_tr = [[hist_mm * (0.6 + 0.1 * (i + j) % 5) for j in range(7)] for i in range(len(traces))]
    shuffled = schaake_shuffle(traces, hist_tr) if traces else []
    pinball = None
    if y_true is not None:
        pinball = {str(t): round(pinball_loss(y_true, blended[t], t), 4) for t in QUANTILES}
    q50 = blended[0.5]
    return {
        "method": "EQMN",
        "eqmn": True,
        "blend": "Q(τ)=Σ w_k Q_k(τ)",
        "q10": blended[0.1],
        "q25": blended[0.25],
        "q50": q50,
        "q75": blended[0.75],
        "q90": blended[0.9],
        "q95": blended[0.95],
        "q99": blended[0.99],
        "quantiles": {str(t): blended[t] for t in QUANTILES},
        "mean": vin.get("mean"),
        "pdf_x": xs,
        "pdf_y": pdf,
        "mixture": "diagnostic p(y)=Σ w_k N(μ_k, σ_k²) — not the operational blend",
        "pinball": pinball,
        "extremes": {
            "p_ge_64_5": round(heavy, 4),
            "p_ge_115_6": round(vheavy, 4),
            "p_ge_204_5": round(extreme, 4),
            "p_ge_64_5_gaussian": round(heavy_g, 4),
            "p_ge_115_6_gaussian": round(vheavy_g, 4),
            "p_ge_204_5_gaussian": round(extreme_g, 4),
            "thresholds_mm": [RAIN_HEAVY_MM, RAIN_VERY_HEAVY_DOC, RAIN_EXTREME_MM],
            "classifier": "IMD heavy / very heavy / extreme",
        },
        "schaake": {"n_traces": len(shuffled), "leads": len(shuffled[0]) if shuffled else 0},
        "members_used": ids,
        "temp": _branch(members, weights, "temp_max", 40.0, allow_negative=True),
        "wind": _branch(members, weights, "wind_max", 60.0),
    }


def _branch(
    members: dict[str, dict],
    weights: dict[str, float],
    key: str,
    thresh: float,
    *,
    allow_negative: bool = False,
) -> dict[str, Any]:
    ids, mus, ws = [], [], []
    for sid, pack in members.items():
        ser = pack.get(key) or []
        if ser and sid in weights:
            ids.append(sid)
            mus.append(float(ser[0]))
            ws.append(float(weights[sid]))
    if not mus:
        return {"q10": None, "q50": None, "q90": None, "q95": None, "q99": None, "p_exceed": 0.0, "threshold": thresh, "n": 0, "method": "EQMN"}
    sigs = [max(1.0, abs(m) * 0.12 + 0.8) for m in mus]
    model_qs = []
    for m, s in zip(mus, sigs):
        q = member_quantiles(m, s)
        if allow_negative:
            q = {t: (m - 1.28 * s if t <= 0.1 else m if t == 0.5 else m + (2.33 if t >= 0.99 else 1.64) * s * ((t - 0.5) / 0.5)) for t in QUANTILES}
            prev = None
            fixed = {}
            for t in QUANTILES:
                v = q[t]
                if prev is not None:
                    v = max(v, prev)
                fixed[t] = v
                prev = v
            q = fixed
        model_qs.append(q)
    blended = blend_quantiles(model_qs, ws)
    p_q = p_from_quantiles(blended, thresh)
    p_g = p_exceed(mus, thresh, ws)
    return {
        "q10": blended[0.1],
        "q50": blended[0.5],
        "q90": blended[0.9],
        "q95": blended[0.95],
        "q99": blended[0.99],
        "p_exceed": round(max(p_q, p_g * 0.5), 3),
        "threshold": thresh,
        "n": len(mus),
        "method": "EQMN",
    }

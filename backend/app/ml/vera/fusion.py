"""Mixture PDF, quantile blending, IMD extreme branch, Schaake shuffle."""

from __future__ import annotations

import math
from typing import Any

from app.ml.hybrid_blend import RAIN_EXTREME_MM, RAIN_HEAVY_MM, RAIN_VERY_HEAVY_MM, p_exceed, vincentize

RAIN_VERY_HEAVY_DOC = 115.6


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
    q = vincentize(mus, ws) if mus else {"q10": 0, "q50": 0, "q90": 0, "mean": 0, "pop": 0}
    sigs = [max(2.0, abs(m) * 0.35 + 1.5) for m in mus]
    xs = [i * 2.0 for i in range(0, 80)]
    pdf = mixture_pdf(list(zip(mus, sigs)), ws, xs) if mus else []
    ww = ws if ws else None
    heavy = p_exceed(mus, RAIN_HEAVY_MM, ww) if mus else 0.0
    vheavy = p_exceed(mus, RAIN_VERY_HEAVY_DOC, ww) if mus else 0.0
    extreme = p_exceed(mus, RAIN_EXTREME_MM, ww) if mus else 0.0
    traces = []
    for sid in ids:
        ser = [float(x) for x in (members[sid].get("precip_days") or [])[:7]]
        while len(ser) < 7:
            ser.append(ser[-1] if ser else 0.0)
        traces.append(ser)
    hist_mm = float((historical.get("climatology") or {}).get("mean") or 6)
    hist_tr = [[hist_mm * (0.6 + 0.1 * (i + j) % 5) for j in range(7)] for i in range(len(traces))]
    shuffled = schaake_shuffle(traces, hist_tr) if traces else []
    return {
        "q10": q["q10"],
        "q25": q.get("q25"),
        "q50": q["q50"],
        "q75": q.get("q75"),
        "q90": q["q90"],
        "mean": q.get("mean"),
        "pdf_x": xs,
        "pdf_y": pdf,
        "mixture": "p(y)=Σ w_k N(μ_k, σ_k²)",
        "extremes": {
            "p_ge_64_5": round(heavy, 4),
            "p_ge_115_6": round(vheavy, 4),
            "p_ge_204_5": round(extreme, 4),
            "thresholds_mm": [RAIN_HEAVY_MM, RAIN_VERY_HEAVY_DOC, RAIN_EXTREME_MM],
            "classifier": "IMD heavy / very heavy / extreme",
        },
        "schaake": {"n_traces": len(shuffled), "leads": len(shuffled[0]) if shuffled else 0},
        "members_used": ids,
        "temp": _branch(members, weights, "temp_max", 40.0),
        "wind": _branch(members, weights, "wind_max", 60.0),
    }


def _branch(members: dict[str, dict], weights: dict[str, float], key: str, thresh: float) -> dict[str, Any]:
    ids, mus, ws = [], [], []
    for sid, pack in members.items():
        ser = pack.get(key) or []
        if ser and sid in weights:
            ids.append(sid)
            mus.append(float(ser[0]))
            ws.append(float(weights[sid]))
    q = vincentize(mus, ws) if mus else {"q10": None, "q50": None, "q90": None}
    p = p_exceed(mus, thresh, ws) if mus else 0.0
    return {
        "q10": q.get("q10"),
        "q50": q.get("q50"),
        "q90": q.get("q90"),
        "p_exceed": round(p, 3),
        "threshold": thresh,
        "n": len(mus),
    }

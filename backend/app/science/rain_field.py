"""Grid optical-flow + STEPS-style advection on rain / IR fields.

Does not rewrite locked hourly millimetres. Member only: source_kind satellite-nowcast.
"""

from __future__ import annotations

import math
from typing import Any

from app.science.nowcast import _clip
from app.science.sat_cv import ir_rain_mmh


def rain_from_tb(grid: list[list[float]] | None) -> list[list[float]]:
    if not grid:
        return []
    return [[ir_rain_mmh(float(v)) for v in row] for row in grid]


def _bilinear(g: list[list[float]], y: float, x: float) -> float:
    h, w = len(g), len(g[0])
    if h < 2 or w < 2:
        return 0.0
    y0 = int(math.floor(y))
    x0 = int(math.floor(x))
    y1, x1 = y0 + 1, x0 + 1
    if y0 < 0 or x0 < 0 or y1 >= h or x1 >= w:
        return 0.0
    wy, wx = y - y0, x - x0
    a = g[y0][x0] * (1 - wx) + g[y0][x1] * wx
    b = g[y1][x0] * (1 - wx) + g[y1][x1] * wx
    return a * (1 - wy) + b * wy


def optical_flow(prev: list[list[float]], curr: list[list[float]], step: int = 4) -> dict[str, float]:
    """Coarse block-match flow. dx+ east (column), dy+ south (row)."""
    if not prev or not curr or not prev[0] or not curr[0]:
        return {"u_px": 0.0, "v_px": 0.0, "speed_px": 0.0, "method": "no-grid"}
    if len(prev) != len(curr) or len(prev[0]) != len(curr[0]):
        return {"u_px": 0.0, "v_px": 0.0, "speed_px": 0.0, "method": "shape-mismatch"}
    h, w = len(curr), len(curr[0])
    best = (0, 0)
    best_s = 1e18
    for dy in range(-3, 4):
        for dx in range(-3, 4):
            s = 0.0
            n = 0
            y = 0
            while y + step < h:
                x = 0
                while x + step < w:
                    a = curr[y][x]
                    yy, xx = y + dy, x + dx
                    if 0 <= yy < h and 0 <= xx < w and a > 0.15:
                        s += abs(a - prev[yy][xx])
                        n += 1
                    x += step
                y += step
            if n:
                s /= n
                if s < best_s:
                    best_s = s
                    best = (dx, dy)
    u, v = float(best[0]), float(best[1])
    return {
        "u_px": u,
        "v_px": v,
        "speed_px": round(math.hypot(u, v), 3),
        "sad": round(best_s if best_s < 1e17 else 0.0, 4),
        "method": "block-match rain-field v1",
    }


def _advect_np(g, u: float, v: float):
    """One semi-Lagrangian step: out[y][x] = bilinear(g, y - v, x - u), 0 off-grid.

    u, v are uniform over the grid, so the bilinear weights are the same everywhere and
    the step is a shifted weighted sum. Same arithmetic as ``_bilinear`` but vectorised:
    the pure-Python loop made 1.4M calls per dashboard and held the event loop for ~2 s
    locally (far longer on a Render Free CPU share), timing out /api/ready.
    """
    import numpy as np

    h, w = g.shape
    out = np.zeros((h, w), dtype=np.float64)
    if h < 2 or w < 2:
        return out
    oy = int(math.floor(-v))
    ox = int(math.floor(-u))
    wy = -v - oy
    wx = -u - ox
    ylo, yhi = max(0, -oy), min(h, h - 1 - oy)  # need 0 <= y+oy and y+oy+1 < h
    xlo, xhi = max(0, -ox), min(w, w - 1 - ox)
    if ylo >= yhi or xlo >= xhi:
        return out
    y0 = slice(ylo + oy, yhi + oy)
    y1 = slice(ylo + oy + 1, yhi + oy + 1)
    x0 = slice(xlo + ox, xhi + ox)
    x1 = slice(xlo + ox + 1, xhi + ox + 1)
    a = g[y0, x0] * (1 - wx) + g[y0, x1] * wx
    b = g[y1, x0] * (1 - wx) + g[y1, x1] * wx
    out[ylo:yhi, xlo:xhi] = a * (1 - wy) + b * wy
    return out


def advect(grid: list[list[float]], u: float, v: float, steps: int = 1) -> list[list[float]]:
    if not grid or not grid[0]:
        return []
    import numpy as np

    out = np.asarray(grid, dtype=np.float64)
    for _ in range(max(1, steps)):
        out = _advect_np(out, float(u), float(v))
    return out.tolist()


def steps_ensemble(
    grid: list[list[float]],
    flow: dict[str, float],
    leads: int = 6,
    members: int = 5,
) -> dict[str, Any]:
    """Lagrangian persistence + tiny intensity noise. Mean is the member forecast."""
    u = float(flow.get("u_px") or 0)
    v = float(flow.get("v_px") or 0)
    if not grid:
        return {"hours": [], "spread": None, "n": 0, "method": "no-grid"}
    import numpy as np

    hours: list[dict[str, Any]] = []
    g = np.asarray(grid, dtype=np.float64)
    for lead in range(1, leads + 1):
        fields = []
        for m in range(members):
            jitter_u = u + ((m - members // 2) * 0.15)
            jitter_v = v + ((m % 3) - 1) * 0.15
            adv = _advect_np(g, jitter_u, jitter_v)
            scale = 0.92 + 0.04 * ((m % 3) - 1)
            mean = float(adv.sum()) / max(1, adv.size)
            fields.append(mean * scale)
        g = _advect_np(g, u, v)
        mu = sum(fields) / len(fields)
        var = sum((x - mu) ** 2 for x in fields) / len(fields)
        hours.append(
            {
                "lead_h": lead,
                "mm": round(max(0.0, mu), 3),
                "spread": round(math.sqrt(var), 3),
                "engine": "steps",
            }
        )
    last = hours[-1]["spread"] if hours else None
    return {
        "hours": hours,
        "spread": last,
        "n": members,
        "flow": flow,
        "source_kind": "satellite-nowcast",
        "method": "STEPS-like Lagrangian ensemble v1",
        "note": "Member only. Not a rain-gauge. Does not rewrite locked millimetres.",
    }


def sample_pin(grid: list[list[float]] | None, lat: float, lon: float, bounds: tuple[float, float, float, float] | None) -> float | None:
    if not grid or not grid[0] or not bounds:
        if grid and grid[0]:
            h, w = len(grid), len(grid[0])
            return float(grid[h // 2][w // 2])
        return None
    west, east, south, north = bounds
    h, w = len(grid), len(grid[0])
    if east == west or north == south:
        return float(grid[h // 2][w // 2])
    fx = (lon - west) / (east - west)
    fy = (north - lat) / (north - south)
    x = fx * (w - 1)
    y = fy * (h - 1)
    return round(_bilinear(grid, y, x), 3)


def pack(
    prev_tb: list[list[float]] | None,
    curr_tb: list[list[float]] | None,
    *,
    lat: float,
    lon: float,
    bounds: tuple[float, float, float, float] | None = None,
    imerg_mm_h: float | None = None,
) -> dict[str, Any]:
    curr_r = rain_from_tb(curr_tb) if curr_tb else []
    prev_r = rain_from_tb(prev_tb) if prev_tb else []
    if imerg_mm_h is not None and curr_r:
        # blend a uniform IMERG scale so QPE informs intensity
        scale = float(imerg_mm_h) / max(0.2, sum(sum(r) for r in curr_r) / max(1, len(curr_r) * len(curr_r[0])))
        scale = _clip(scale, 0.25, 4.0)
        curr_r = [[c * scale for c in row] for row in curr_r]
        prev_r = [[c * scale for c in row] for row in prev_r] if prev_r else prev_r
    flow = optical_flow(prev_r, curr_r) if prev_r and curr_r else {"u_px": 0.0, "v_px": 0.0, "speed_px": 0.0, "method": "single-frame"}
    ens = steps_ensemble(curr_r, flow) if curr_r else {"hours": [], "method": "no-grid"}
    pin = sample_pin(curr_r, lat, lon, bounds)
    if pin is None and imerg_mm_h is not None:
        pin = float(imerg_mm_h)
    return {
        "ok": bool(curr_r or imerg_mm_h is not None),
        "pin_mm_h": pin,
        "flow": flow,
        "ensemble": ens,
        "source_kind": "satellite-nowcast",
        "method": "optical-flow + STEPS member v1",
    }

"""Computer vision on IR brightness-temperature grids.

Cells, tracks, IR rain-rate, 15/30/60 min Lagrangian nowcast.
Does not rewrite locked Open-Meteo hourly millimetres.
"""

from __future__ import annotations

import math
from typing import Any

from app.science.nowcast import _clip

DEEP_K = 221.0
COLD_K = 248.0


def _hull_ring(pts: list[tuple[float, float]], lat: float, lon: float, area_km2: float) -> list[list[float]]:
    """Convex hull of cell pixels as a closed [lat, lon] ring. Ellipse if too thin."""
    uniq = sorted(set((round(p[0], 4), round(p[1], 4)) for p in pts))
    if len(uniq) >= 3:
        def cross(o: tuple[float, float], a: tuple[float, float], b: tuple[float, float]) -> float:
            return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])

        lower: list[tuple[float, float]] = []
        for p in uniq:
            while len(lower) >= 2 and cross(lower[-2], lower[-1], p) <= 0:
                lower.pop()
            lower.append(p)
        upper: list[tuple[float, float]] = []
        for p in reversed(uniq):
            while len(upper) >= 2 and cross(upper[-2], upper[-1], p) <= 0:
                upper.pop()
            upper.append(p)
        hull = lower[:-1] + upper[:-1]
        if len(hull) >= 3:
            ring = [[p[0], p[1]] for p in hull]
            ring.append(ring[0])
            return ring
    r_km = math.sqrt(max(area_km2, 40.0) / math.pi)
    r_lat = r_km / 111.3
    r_lon = r_lat / max(0.35, math.cos(math.radians(lat)))
    ring = []
    for i in range(10):
        ang = 2.0 * math.pi * i / 10
        ring.append([round(lat + r_lat * math.sin(ang), 4), round(lon + r_lon * math.cos(ang), 4)])
    ring.append(ring[0])
    return ring


def ir_rain_mmh(tb_k: float) -> float:
    """Adler–Negri / GPI-style IR rain-rate. Cold tops rain harder."""
    if tb_k >= 255:
        return 0.0
    if tb_k <= 200:
        return 48.0
    # linear in Tb from 255→0 to 200→48
    return round(_clip((255.0 - tb_k) / 55.0 * 48.0, 0.0, 60.0), 2)


def _neighbors(y: int, x: int, h: int, w: int) -> list[tuple[int, int]]:
    out = []
    for dy in (-1, 0, 1):
        for dx in (-1, 0, 1):
            if dy == 0 and dx == 0:
                continue
            yy, xx = y + dy, x + dx
            if 0 <= yy < h and 0 <= xx < w:
                out.append((yy, xx))
    return out


def segment(
    tb: list[list[float]],
    *,
    lat0: float | None = None,
    lon0: float | None = None,
    half_deg: float = 1.1,
    bounds: tuple[float, float, float, float] | None = None,
) -> list[dict[str, Any]]:
    if not tb or not tb[0]:
        return []
    h, w = len(tb), len(tb[0])
    seen = [[False] * w for _ in range(h)]
    cells: list[dict[str, Any]] = []
    if bounds:
        west, east, south, north = bounds
    else:
        lat0 = float(lat0 or 0)
        lon0 = float(lon0 or 0)
        west, east = lon0 - half_deg, lon0 + half_deg
        south, north = lat0 - half_deg, lat0 + half_deg

    def lat_of(y: int) -> float:
        return north - (y + 0.5) / h * (north - south)

    def lon_of(x: int) -> float:
        return west + (x + 0.5) / w * (east - west)

    for y in range(h):
        for x in range(w):
            if seen[y][x] or tb[y][x] > COLD_K:
                continue
            stack = [(y, x)]
            seen[y][x] = True
            pts: list[tuple[int, int]] = []
            while stack:
                cy, cx = stack.pop()
                pts.append((cy, cx))
                for ny, nx in _neighbors(cy, cx, h, w):
                    if not seen[ny][nx] and tb[ny][nx] <= COLD_K:
                        seen[ny][nx] = True
                        stack.append((ny, nx))
            if len(pts) < 3:
                continue
            tbs = [tb[py][px] for py, px in pts]
            min_tb = min(tbs)
            sy = sum(p[0] for p in pts) / len(pts)
            sx = sum(p[1] for p in pts) / len(pts)
            deep = sum(1 for v in tbs if v <= DEEP_K)
            area_km2 = len(pts) * ((north - south) * 111.3 / h) * ((east - west) * 111.3 / w)
            clat, clon = lat_of(sy), lon_of(sx)
            step = max(1, len(pts) // 24)
            geo = [(lat_of(py), lon_of(px)) for py, px in pts[::step]]
            cells.append(
                {
                    "id": f"c{len(cells)}",
                    "lat": round(clat, 3),
                    "lon": round(clon, 3),
                    "min_tb_k": round(min_tb, 1),
                    "mean_tb_k": round(sum(tbs) / len(tbs), 1),
                    "area_km2": round(area_km2, 1),
                    "n_pix": len(pts),
                    "deep_frac": round(deep / len(pts), 3),
                    "ot": min_tb <= DEEP_K - 8,
                    "rain_ir_mm_h": ir_rain_mmh(min_tb),
                    "ring": _hull_ring(geo, clat, clon, area_km2),
                }
            )
    cells.sort(key=lambda c: c["min_tb_k"])
    for i, c in enumerate(cells):
        c["id"] = f"c{i}"
    return cells[:40]


def _dist_km(a: dict[str, Any], b: dict[str, Any]) -> float:
    return math.hypot(float(a["lat"]) - float(b["lat"]), float(a["lon"]) - float(b["lon"])) * 111.3


def track(prev: list[dict[str, Any]], cur: list[dict[str, Any]], dt_min: float) -> list[dict[str, Any]]:
    used: set[int] = set()
    dt_h = max(dt_min / 60.0, 1e-3)
    out: list[dict[str, Any]] = []
    for cell in cur:
        best_i = None
        best_d = 80.0
        for i, p in enumerate(prev):
            if i in used:
                continue
            d = _dist_km(cell, p)
            if d < best_d:
                best_d = d
                best_i = i
        u_kmh = v_kmh = 0.0
        d_tb = 0.0
        d_area = 0.0
        parent = None
        if best_i is not None:
            used.add(best_i)
            p = prev[best_i]
            parent = p.get("id")
            u_kmh = (float(cell["lon"]) - float(p["lon"])) * 111.3 / dt_h
            v_kmh = (float(cell["lat"]) - float(p["lat"])) * 111.3 / dt_h
            d_tb = float(cell["min_tb_k"]) - float(p["min_tb_k"])
            d_area = float(cell["area_km2"]) - float(p.get("area_km2") or 0)
        speed = math.hypot(u_kmh, v_kmh)
        if d_tb <= -1.5 or d_area > 40:
            trend = "growing"
        elif d_tb >= 2.0 or d_area < -40:
            trend = "collapsing"
        else:
            trend = "steady"
        out.append(
            {
                **cell,
                "u_kmh": round(u_kmh, 2),
                "v_kmh": round(v_kmh, 2),
                "speed_kmh": round(speed, 2),
                "d_tb_k": round(d_tb, 2),
                "d_area_km2": round(d_area, 1),
                "trend": trend,
                "parent": parent,
            }
        )
    return out


def forecast_track(cell: dict[str, Any], minutes: tuple[int, ...] = (15, 30, 60)) -> list[dict[str, Any]]:
    u = float(cell.get("u_kmh") or 0)
    v = float(cell.get("v_kmh") or 0)
    trend = cell.get("trend") or "steady"
    rain0 = float(cell.get("rain_ir_mm_h") or 0)
    rows = []
    for m in minutes:
        dt_h = m / 60.0
        rain = rain0
        if trend == "growing":
            rain *= 1.0 + 0.15 * (m / 30.0)
        elif trend == "collapsing":
            rain *= max(0.2, 1.0 - 0.25 * (m / 30.0))
        rows.append(
            {
                "lead_min": m,
                "lat": round(float(cell["lat"]) + v * dt_h / 111.3, 3),
                "lon": round(float(cell["lon"]) + u * dt_h / 111.3, 3),
                "rain_ir_mm_h": round(min(70.0, rain), 2),
            }
        )
    return rows


def pin_eta_min(cell: dict[str, Any], lat: float, lon: float) -> int | None:
    u = float(cell.get("u_kmh") or 0)
    v = float(cell.get("v_kmh") or 0)
    if abs(u) + abs(v) < 2:
        d = _dist_km(cell, {"lat": lat, "lon": lon})
        return 0 if d < 25 else None
    best = None
    for m in range(0, 75, 5):
        dt_h = m / 60.0
        plat = float(cell["lat"]) + v * dt_h / 111.3
        plon = float(cell["lon"]) + u * dt_h / 111.3
        d = math.hypot(plat - lat, plon - lon) * 111.3
        rad = max(18.0, math.sqrt(max(cell.get("area_km2") or 80, 80) / math.pi))
        if d <= rad:
            return m
        if best is None or d < best[1]:
            best = (m, d)
    return None


def associate_strokes(cells: list[dict[str, Any]], strokes: list[dict[str, Any]], max_km: float = 25.0) -> None:
    for s in strokes:
        best = None
        best_d = max_km
        for c in cells:
            d = _dist_km(c, s)
            if d < best_d:
                best_d = d
                best = c["id"]
        s["cell_id"] = best
        s["cell_km"] = None if best is None else round(best_d, 1)

"""Computer vision on IR brightness-temperature grids.

Cells, ForTraCC-style overlap tracks, Hydro-Estimator-lite IR rain-rate,
15/30/60 min Lagrangian nowcast.

Does not rewrite locked Open-Meteo hourly millimetres.
Public JPEG Tb is a display proxy, not MOSDAC HEM.
"""

from __future__ import annotations

import math
from typing import Any

from app.science.nowcast import _clip

DEEP_K = 221.0
# ForTraCC / IMD MCS core (Vila 2008, Goyal et al. 2017).
CORE_K = 235.0
# Cold anvil halo — not a storm object on its own.
COLD_K = 248.0
INSAT_SUB_LON = 82.0
OVERLAP_MIN = 0.15


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


def ir_rain_mmh(
    tb_k: float,
    surround_tb: float | None = None,
    *,
    cooling_k: float = 0.0,
    ot: bool = False,
) -> float:
    """Hydro-Estimator-lite IR rain-rate.

    Rain only when the pixel is colder than its surroundings (HE core vs anvil).
    One-arg form keeps GPI-style colder-is-heavier for tests and pin samples.
    Not a rain-gauge and not MOSDAC HEM millimetres.
    """
    if tb_k >= 255:
        return 0.0
    if surround_tb is not None and tb_k > float(surround_tb) - 6.0:
        return 0.0
    if tb_k <= 200:
        base = 48.0
    else:
        base = _clip((255.0 - tb_k) / 55.0 * 48.0, 0.0, 60.0)
    if surround_tb is not None:
        contrast = max(0.0, float(surround_tb) - tb_k)
        base *= _clip(contrast / 18.0, 0.35, 1.35)
    if ot:
        base *= 1.12
    if cooling_k >= 1.2:
        base *= 1.10
    return round(_clip(base, 0.0, 60.0), 2)


def parallax_nudge(lat: float, lon: float, *, ot: bool = False, min_tb_k: float | None = None) -> tuple[float, float]:
    """Shift apparent IR position toward INSAT sub-satellite point (~82°E).

    High Cb appears displaced away from nadir. ~0.08–0.12° at 12 km, 30°N.
    """
    high = ot or (min_tb_k is not None and float(min_tb_k) <= DEEP_K)
    if not high:
        return round(lat, 3), round(lon, 3)
    dlat = float(lat) - 0.0
    dlon = float(lon) - INSAT_SUB_LON
    factor = 0.0035
    return round(float(lat) - dlat * factor, 3), round(float(lon) - dlon * factor, 3)


def _ot_flag(tb: list[list[float]], y: int, x: int, min_tb: float) -> bool:
    """SATMET-style overshooting top: local Tb min plus sharp gradient."""
    if min_tb > DEEP_K:
        return False
    h, w = len(tb), len(tb[0])
    vals: list[float] = []
    for dy in range(-2, 3):
        for dx in range(-2, 3):
            if dy == 0 and dx == 0:
                continue
            yy, xx = y + dy, x + dx
            if 0 <= yy < h and 0 <= xx < w:
                vals.append(tb[yy][xx])
    if not vals:
        return min_tb <= DEEP_K - 8
    return (sum(vals) / len(vals) - min_tb) >= 8.0


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


def _surround_tb(tb: list[list[float]], pts: list[tuple[int, int]]) -> float:
    """Mean Tb of a 1-pixel ring around the cell (Hydro-Estimator neighbourhood)."""
    h, w = len(tb), len(tb[0])
    core = set(pts)
    ring: list[float] = []
    for y, x in pts:
        for ny, nx in _neighbors(y, x, h, w):
            if (ny, nx) not in core:
                ring.append(tb[ny][nx])
    if not ring:
        return 255.0
    return sum(ring) / len(ring)


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

    def _emit(pts: list[tuple[int, int]], layer: str) -> None:
        if len(pts) < 3:
            return
        tbs = [tb[py][px] for py, px in pts]
        min_tb = min(tbs)
        sy = sum(p[0] for p in pts) / len(pts)
        sx = sum(p[1] for p in pts) / len(pts)
        deep = sum(1 for v in tbs if v <= DEEP_K)
        area_km2 = len(pts) * ((north - south) * 111.3 / h) * ((east - west) * 111.3 / w)
        clat, clon = lat_of(sy), lon_of(sx)
        min_i = min(range(len(pts)), key=lambda i: tb[pts[i][0]][pts[i][1]])
        ot = _ot_flag(tb, pts[min_i][0], pts[min_i][1], min_tb) if layer == "core" else False
        surround = _surround_tb(tb, pts)
        clat, clon = parallax_nudge(clat, clon, ot=ot, min_tb_k=min_tb)
        step = max(1, len(pts) // 24)
        geo = [(lat_of(py), lon_of(px)) for py, px in pts[::step]]
        pix_step = max(1, len(pts) // 80)
        pix = [py * 1024 + px for py, px in pts[::pix_step]]
        cells.append(
            {
                "id": f"c{len(cells)}",
                "lat": round(clat, 3),
                "lon": round(clon, 3),
                "min_tb_k": round(min_tb, 1),
                "mean_tb_k": round(sum(tbs) / len(tbs), 1),
                "surround_tb_k": round(surround, 1),
                "area_km2": round(area_km2, 1),
                "n_pix": len(pts),
                "deep_frac": round(deep / len(pts), 3),
                "ot": ot,
                "layer": layer,
                "kind": "cloud" if layer == "anvil" else None,
                "rain_ir_mm_h": ir_rain_mmh(min_tb, surround, ot=ot),
                "source_kind": "ir-proxy",
                "ring": _hull_ring(geo, clat, clon, area_km2),
                "pix": pix,
            }
        )

    for y in range(h):
        for x in range(w):
            if seen[y][x] or tb[y][x] > CORE_K:
                continue
            stack = [(y, x)]
            seen[y][x] = True
            pts: list[tuple[int, int]] = []
            while stack:
                cy, cx = stack.pop()
                pts.append((cy, cx))
                for ny, nx in _neighbors(cy, cx, h, w):
                    if not seen[ny][nx] and tb[ny][nx] <= CORE_K:
                        seen[ny][nx] = True
                        stack.append((ny, nx))
            _emit(pts, "core")
    for y in range(h):
        for x in range(w):
            if seen[y][x] or tb[y][x] > COLD_K:
                continue
            stack = [(y, x)]
            seen[y][x] = True
            pts = []
            while stack:
                cy, cx = stack.pop()
                pts.append((cy, cx))
                for ny, nx in _neighbors(cy, cx, h, w):
                    if not seen[ny][nx] and tb[ny][nx] <= COLD_K:
                        seen[ny][nx] = True
                        stack.append((ny, nx))
            if len(pts) >= 4:
                _emit(pts, "anvil")
    cells.sort(key=lambda c: (0 if c.get("layer") == "core" else 1, c["min_tb_k"]))
    for i, c in enumerate(cells):
        c["id"] = f"c{i}"
    return cells[:80]


def _dist_km(a: dict[str, Any], b: dict[str, Any]) -> float:
    return math.hypot(float(a["lat"]) - float(b["lat"]), float(a["lon"]) - float(b["lon"])) * 111.3


def _pix_set(cell: dict[str, Any]) -> set[int]:
    raw = cell.get("pix")
    if isinstance(raw, list):
        out: set[int] = set()
        for v in raw:
            try:
                out.add(int(v))
            except (TypeError, ValueError):
                continue
        return out
    return set()


def _overlap_frac(a: dict[str, Any], b: dict[str, Any]) -> float:
    sa, sb = _pix_set(a), _pix_set(b)
    if not sa or not sb:
        return 0.0
    inter = len(sa & sb)
    return inter / max(1, min(len(sa), len(sb)))


def track(prev: list[dict[str, Any]], cur: list[dict[str, Any]], dt_min: float) -> list[dict[str, Any]]:
    """ForTraCC overlap tracking with centroid fallback (Vila 2008)."""
    used: set[int] = set()
    dt_h = max(dt_min / 60.0, 1e-3)
    out: list[dict[str, Any]] = []
    for cell in cur:
        best_i = None
        best_score = -1.0
        for i, p in enumerate(prev):
            if i in used:
                continue
            frac = _overlap_frac(cell, p)
            if frac >= OVERLAP_MIN:
                if frac > best_score:
                    best_score = frac
                    best_i = i
                continue
            if best_score >= OVERLAP_MIN:
                continue
            d = _dist_km(cell, p)
            score = (1.0 - d / 80.0) * 0.5 if d < 80.0 else -1.0
            if score > best_score:
                best_score = score
                best_i = i
        u_kmh = v_kmh = 0.0
        d_tb = 0.0
        d_area = 0.0
        parent = None
        age = float(dt_min)
        first_seen = cell.get("first_seen")
        if best_i is not None and best_score >= 0:
            used.add(best_i)
            p = prev[best_i]
            parent = p.get("id")
            u_kmh = (float(cell["lon"]) - float(p["lon"])) * 111.3 / dt_h
            v_kmh = (float(cell["lat"]) - float(p["lat"])) * 111.3 / dt_h
            d_tb = float(cell["min_tb_k"]) - float(p["min_tb_k"])
            d_area = float(cell.get("area_km2") or 0) - float(p.get("area_km2") or 0)
            try:
                age = float(p.get("age_min") or 0) + float(dt_min)
            except (TypeError, ValueError):
                age = float(dt_min)
            first_seen = p.get("first_seen") or first_seen
            if p.get("id"):
                cell = {**cell, "id": p.get("id")}
        speed = math.hypot(u_kmh, v_kmh)
        if d_tb <= -1.5 or d_area > 40:
            trend = "growing"
        elif d_tb >= 2.0 or d_area < -40:
            trend = "collapsing"
        else:
            trend = "steady"
        rain = ir_rain_mmh(
            float(cell.get("min_tb_k") or 250),
            cell.get("surround_tb_k"),
            cooling_k=-d_tb,
            ot=bool(cell.get("ot")),
        )
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
                "age_min": round(age, 1),
                "first_seen": first_seen,
                "rain_ir_mm_h": rain,
                "overlap": round(best_score, 3) if best_score >= 0 else None,
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

"""Two-frame IR nowcast: cooling, block-match flow, lightning-jump, cloudburst.

Breakthrough vs a single static IR snapshot:
  • persist the last India Tb grid
  • cooling = prev − curr (K / frame)
  • 8×8 block-match gives a motion field (not just cell centroids)
  • Schultz 2σ lightning-jump on strokes associated to the cell (not OT pixels)
  • LightningCast-lite logistic on VIS/SWIR/TIR patch stats (Cintineo 2022)
  • cloudburst = stall + cooling + deep top + orographic boost

Does not invent locked hourly millimetres. Does not fake GPS strokes.
"""

from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from typing import Any

from app.config import ROOT
from app.data.physiography import classify
from app.science import sat_cv
from app.science.nowcast import _clip

FRAME_PATH = ROOT / ".cache" / "ir_frames.json"
OT_K = 213.0
DEEP_K = 221.0


def _load() -> dict[str, Any]:
    if not FRAME_PATH.exists():
        return {}
    try:
        return json.loads(FRAME_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def _save(blob: dict[str, Any]) -> None:
    FRAME_PATH.parent.mkdir(parents=True, exist_ok=True)
    FRAME_PATH.write_text(json.dumps(blob), encoding="utf-8")


def _mean(vals: list[float]) -> float:
    return sum(vals) / len(vals) if vals else 0.0


def block_flow(prev: list[list[float]], curr: list[list[float]], step: int = 8) -> tuple[float, float]:
    """Coarse optical-flow: best 8×8 block shift on the coldest half of the grid."""
    if not curr or not curr[0]:
        return 0.0, 0.0
    h, w = len(curr), len(curr[0])
    if len(prev) != h or not prev[0] or len(prev[0]) != w:
        return 0.0, 0.0
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
                    if 0 <= yy < h and 0 <= xx < w and a <= 248:
                        s += abs(a - prev[yy][xx])
                        n += 1
                    x += step
                y += step
            if n:
                s /= n
                if s < best_s:
                    best_s = s
                    best = (dx, dy)
    return float(best[0]), float(best[1])


def cooling_stats(prev: list[list[float]], curr: list[list[float]]) -> dict[str, float]:
    if not curr or not curr[0]:
        return {"d_tb": 0.0, "n_cold": 0.0, "n_ot": 0.0, "jump": 0.0}
    h, w = len(curr), len(curr[0])
    cool = 0.0
    n_cold = 0
    n_ot = 0
    n_ot_prev = 0
    for y in range(min(h, len(prev))):
        pw = prev[y]
        cw = curr[y]
        for x in range(min(w, len(pw), len(cw))):
            if cw[x] <= 248:
                cool += pw[x] - cw[x]
                n_cold += 1
            if cw[x] <= OT_K:
                n_ot += 1
            if pw[x] <= OT_K:
                n_ot_prev += 1
    return {
        "d_tb": round(cool / n_cold, 2) if n_cold else 0.0,
        "n_cold": n_cold,
        "n_ot": n_ot,
        "jump": n_ot - n_ot_prev,
    }


def schultz_jump(strokes: list[dict[str, Any]], area_km2: float = 100.0) -> dict[str, Any]:
    """Schultz et al. 2009 2σ lightning jump on flash rate, area-normalized (FRarea).

    Needs a per-cell stroke time series. OT pixel delta is not a jump.
    """
    empty = {"jump": False, "dfrdt": 0.0, "sigma": 0.0, "fr_per_min": 0.0, "n": 0}
    if not strokes:
        return empty
    ages: list[float] = []
    for s in strokes:
        if s.get("past_mins") is not None:
            try:
                ages.append(float(s["past_mins"]))
                continue
            except (TypeError, ValueError):
                pass
        raw = s.get("t") or s.get("timestamp_utc")
        if raw:
            try:
                t = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
                if t.tzinfo is None:
                    t = t.replace(tzinfo=timezone.utc)
                ages.append(max(0.0, (datetime.now(timezone.utc) - t).total_seconds() / 60.0))
            except ValueError:
                ages.append(5.0)
        else:
            ages.append(5.0)
    ages = [a for a in ages if 0 <= a <= 20]
    if len(ages) < 2:
        return {**empty, "n": len(ages)}
    bins = [0, 0, 0, 0, 0]  # 0-4, 4-8, 8-12, 12-16, 16-20 min ago
    for a in ages:
        bins[min(4, int(a // 4))] += 1
    # flash rate per 4 min, newest last
    fr = [bins[i] / 4.0 for i in range(4, -1, -1)]
    area = max(float(area_km2) or 80.0, 40.0)
    fr_area = [x / (area / 100.0) for x in fr]
    dfrdt = [fr_area[i] - fr_area[i - 1] for i in range(1, len(fr_area))]
    if len(dfrdt) < 2:
        return {**empty, "n": len(ages), "fr_per_min": round(fr[-1], 3)}
    mu = _mean(dfrdt[:-1])
    var = _mean([(x - mu) ** 2 for x in dfrdt[:-1]])
    sigma = math.sqrt(var) if var > 0 else 0.15
    last = dfrdt[-1]
    jumped = last > (2.0 * sigma) and fr[-1] >= 0.5
    return {
        "jump": jumped,
        "dfrdt": round(last, 3),
        "sigma": round(sigma, 3),
        "fr_per_min": round(fr[-1], 3),
        "n": len(ages),
        "method": "schultz-2sigma-frarea",
    }


def lightningcast_lite(
    cell: dict[str, Any],
    cool: dict[str, float] | None = None,
    bands: dict[str, Any] | None = None,
) -> float:
    """Cintineo LightningCast-style logistic on public INSAT JPEG stats.

    VIS + SWIR + TIR when bands exist; TIR + cooling otherwise.
    Not a trained GOES-R CNN.
    """
    tb = float(cell.get("min_tb_k") or 300)
    z = -1.6
    z += _clip((240.0 - tb) / 28.0, -0.4, 2.2)
    if cell.get("ot"):
        z += 0.55
    cool = cool or {}
    if float(cool.get("d_tb") or 0) >= 1.2:
        z += 0.45
    vis = swir = None
    if isinstance(bands, dict):
        for b in bands.get("bands") or []:
            if not isinstance(b, dict) or not b.get("ok"):
                continue
            name = str(b.get("channel") or "")
            if name.startswith("VIS"):
                vis = b.get("gray")
            elif name.startswith("SWIR"):
                swir = b.get("gray")
        if vis is not None:
            # textured / bright visible glaciated tops
            z += _clip((float(vis) - 90.0) / 80.0, -0.2, 0.6)
        if swir is not None:
            z += _clip((140.0 - float(swir)) / 90.0, -0.15, 0.4)
    p = 1.0 / (1.0 + math.exp(-z))
    return round(_clip(p, 0.04, 0.92), 3)


def lightning_prob(
    cell: dict[str, Any],
    cool: dict[str, float],
    flow_speed: float,
    *,
    strokes: list[dict[str, Any]] | None = None,
    bands: dict[str, Any] | None = None,
) -> float:
    """P(lightning in 0–60 min). Blend of IR heuristic, LightningCast-lite, Schultz jump."""
    p = 0.08
    tb = float(cell.get("min_tb_k") or 300)
    if tb <= OT_K:
        p += 0.28
    elif tb <= DEEP_K:
        p += 0.16
    if cell.get("ot"):
        p += 0.12
    if cool.get("d_tb", 0) >= 1.2:
        p += 0.18
    if float(cell.get("rain_ir_mm_h") or 0) >= 12:
        p += 0.10
    if flow_speed < 12:
        p += 0.06
    p = _clip(p, 0.04, 0.90)
    lc = lightningcast_lite(cell, cool, bands)
    jump = schultz_jump(strokes or [], float(cell.get("area_km2") or 100))
    p_jump = 0.22 if jump.get("jump") else 0.0
    # Do not let OT-pixel "jump" (cool['jump']) substitute for Schultz.
    blended = 0.50 * p + 0.35 * lc + 0.15 * (0.55 + p_jump)
    return round(_clip(blended, 0.04, 0.92), 3)


def cloudburst_prob(cell: dict[str, Any], cool: dict[str, float], phys_kind: str) -> float:
    p = 0.06
    tb = float(cell.get("min_tb_k") or 300)
    rain = float(cell.get("rain_ir_mm_h") or 0)
    speed = float(cell.get("speed_kmh") or 99)
    if tb <= DEEP_K:
        p += 0.22
    if rain >= 18:
        p += 0.20
    elif rain >= 8:
        p += 0.10
    if speed <= 14:
        p += 0.16
    if cool.get("d_tb", 0) >= 1.5:
        p += 0.16
    if phys_kind == "orographic":
        p += 0.18
    elif phys_kind == "hugli":
        p += 0.06
    if cell.get("trend") == "growing":
        p += 0.10
    if tb > DEEP_K and phys_kind != "orographic":
        p = min(p, 0.35)
    return round(_clip(p, 0.04, 0.94), 3)


def enhance(
    cells: list[dict[str, Any]],
    grid: list[list[float]] | None,
    bounds: tuple[float, float, float, float] | None,
    *,
    strokes: list[dict[str, Any]] | None = None,
    bands: dict[str, Any] | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Attach flow, lightning-jump and cloudburst probabilities. Persist grid."""
    meta = {"frames": 1, "d_tb": 0.0, "jump": 0, "u_px": 0.0, "v_px": 0.0}
    if not grid:
        return cells, meta
    store = _load()
    prev = store.get("grid")
    prev_t = store.get("t")
    prev_cells = list(store.get("cells") or [])
    if not prev_cells:
        try:
            from app.science.cv_memory import last_ir_cells

            prev_cells = last_ir_cells()
        except Exception:
            prev_cells = []
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    cool = {"d_tb": 0.0, "jump": 0, "n_ot": 0, "n_cold": 0}
    u_px = v_px = 0.0
    dt_min = 10.0
    if prev and prev_t:
        try:
            dt_min = max(
                4.0,
                (
                    datetime.now(timezone.utc)
                    - datetime.fromisoformat(str(prev_t).replace("Z", "+00:00"))
                ).total_seconds()
                / 60.0,
            )
        except ValueError:
            dt_min = 10.0
        cool = cooling_stats(prev, grid)
        u_px, v_px = block_flow(prev, grid)
        meta = {
            "frames": 2,
            "d_tb": cool["d_tb"],
            "jump": cool["jump"],
            "u_px": u_px,
            "v_px": v_px,
            "dt_min": round(dt_min, 1),
        }
    if prev_cells and cells and not all(c.get("trend") for c in cells):
        cells = sat_cv.track(prev_cells, cells, dt_min)
    try:
        slim = [
            {
                k: c.get(k)
                for k in (
                    "id",
                    "lat",
                    "lon",
                    "min_tb_k",
                    "area_km2",
                    "pix",
                    "ot",
                    "age_min",
                    "first_seen",
                    "last_seen",
                    "surround_tb_k",
                )
            }
            for c in cells
        ]
        _save({"t": prev_t or now, "grid": grid, "prev": prev, "bounds": bounds, "cells": slim})
        try:
            from app.science.cv_memory import remember_frame

            remember_frame(slim, now)
        except Exception:
            pass
    except OSError:
        pass
    except Exception:
        pass

    west, east, south, north = bounds or (68.0, 97.5, 6.5, 37.2)
    h = max(len(grid), 1)
    w = max(len(grid[0]), 1)
    km_x = (east - west) * 111.3 / w
    km_y = (north - south) * 111.3 / h
    flow_u = u_px * km_x / (dt_min / 60.0) if dt_min else 0.0
    flow_v = -v_px * km_y / (dt_min / 60.0) if dt_min else 0.0
    flow_speed = math.hypot(flow_u, flow_v)

    strokes = list(strokes or [])
    out = []
    for c in cells:
        phys = classify(float(c["lat"]), float(c["lon"]))
        tracked = sat_cv.track([], [c], dt_min)[0] if not c.get("trend") else c
        if abs(float(tracked.get("u_kmh") or 0)) + abs(float(tracked.get("v_kmh") or 0)) < 1:
            tracked["u_kmh"] = round(flow_u, 2)
            tracked["v_kmh"] = round(flow_v, 2)
            tracked["speed_kmh"] = round(flow_speed, 2)
        cid = tracked.get("id")
        cell_strokes = [s for s in strokes if s.get("cell_id") == cid] or [
            s
            for s in strokes
            if sat_cv._dist_km(tracked, s) <= 25
        ]
        jump = schultz_jump(cell_strokes, float(tracked.get("area_km2") or 100))
        lp = lightning_prob(
            tracked,
            cool,
            float(tracked.get("speed_kmh") or flow_speed),
            strokes=cell_strokes,
            bands=bands,
        )
        cp = cloudburst_prob(tracked, cool, str(phys.get("kind") or ""))
        seed = tracked.get("kind")
        d_tb = float(tracked.get("d_tb_k") or c.get("d_tb_k") or 0)
        trend = tracked.get("trend") or c.get("trend")
        collapsing = trend == "collapsing" or (d_tb >= 2.0 and trend != "growing")
        if cp >= 0.55:
            kind = "cloudburst"
        elif collapsing:
            kind = "downburst"
        elif lp >= 0.32:
            kind = "lightning"
        elif tracked.get("ot") or cp >= 0.28 or lp >= 0.22:
            kind = "storm"
        elif seed == "cloud" or tracked.get("layer") == "anvil" or (float(tracked.get("min_tb_k") or 300) <= 248 and not tracked.get("ot")):
            kind = "cloud"
        else:
            kind = seed or "storm"
        out.append(
            {
                **tracked,
                "kind": kind,
                "p_lightning": lp,
                "p_cloudburst": cp,
                "schultz": jump,
                "phys": phys.get("kind"),
                "engine": "cv-nowcast-v2",
            }
        )
    meta["schultz_cells"] = sum(1 for c in out if (c.get("schultz") or {}).get("jump"))
    return out, meta

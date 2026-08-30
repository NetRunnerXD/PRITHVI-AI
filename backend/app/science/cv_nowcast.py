"""Two-frame IR nowcast: cooling, block-match flow, lightning-jump, cloudburst.

Breakthrough vs a single static IR snapshot:
  • persist the last India Tb grid
  • cooling = prev − curr (K / frame)
  • 8×8 block-match gives a motion field (not just cell centroids)
  • lightning-jump = rapid growth of overshooting-top area
  • cloudburst = stall + cooling + deep top + orographic boost

Does not invent locked hourly millimetres. Does not fake GPS strokes.
"""

from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from pathlib import Path
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
    for dy in range(-2, 3):
        for dx in range(-2, 3):
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
    # dx+ = east, dy+ = south on the image
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


def lightning_prob(cell: dict[str, Any], cool: dict[str, float], flow_speed: float) -> float:
    """P(lightning in 0–60 min) from OT, cooling, jump, rain-rate. Not a stroke."""
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
    if cool.get("jump", 0) >= 2:
        p += 0.22
    if float(cell.get("rain_ir_mm_h") or 0) >= 12:
        p += 0.10
    if flow_speed < 12:
        p += 0.06
    return round(_clip(p, 0.04, 0.92), 3)


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
    return round(_clip(p, 0.04, 0.94), 3)


def enhance(
    cells: list[dict[str, Any]],
    grid: list[list[float]] | None,
    bounds: tuple[float, float, float, float] | None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Attach flow, lightning-jump and cloudburst probabilities. Persist grid."""
    meta = {"frames": 1, "d_tb": 0.0, "jump": 0, "u_px": 0.0, "v_px": 0.0}
    if not grid:
        return cells, meta
    store = _load()
    prev = store.get("grid")
    prev_t = store.get("t")
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
    try:
        _save({"t": now, "grid": grid, "bounds": bounds})
    except OSError:
        pass

    west, east, south, north = bounds or (68.0, 97.5, 6.5, 37.2)
    h = max(len(grid), 1)
    w = max(len(grid[0]), 1)
    # pixel shift → km/h
    km_x = (east - west) * 111.3 / w
    km_y = (north - south) * 111.3 / h
    flow_u = u_px * km_x / (dt_min / 60.0) if dt_min else 0.0
    flow_v = -v_px * km_y / (dt_min / 60.0) if dt_min else 0.0
    flow_speed = math.hypot(flow_u, flow_v)

    out = []
    for c in cells:
        phys = classify(float(c["lat"]), float(c["lon"]))
        tracked = sat_cv.track([], [c], dt_min)[0] if not c.get("trend") else c
        if abs(float(tracked.get("u_kmh") or 0)) + abs(float(tracked.get("v_kmh") or 0)) < 1:
            tracked["u_kmh"] = round(flow_u, 2)
            tracked["v_kmh"] = round(flow_v, 2)
            tracked["speed_kmh"] = round(flow_speed, 2)
        lp = lightning_prob(tracked, cool, float(tracked.get("speed_kmh") or flow_speed))
        cp = cloudburst_prob(tracked, cool, str(phys.get("kind") or ""))
        kind = tracked.get("kind") or "storm"
        if cp >= 0.55:
            kind = "cloudburst"
        elif tracked.get("trend") == "collapsing" and lp >= 0.35:
            kind = "downburst"
        elif lp >= 0.32:
            kind = "lightning"
        elif tracked.get("ot") or cp >= 0.28 or lp >= 0.22:
            kind = "storm"
        out.append(
            {
                **tracked,
                "kind": kind,
                "p_lightning": lp,
                "p_cloudburst": cp,
                "phys": phys.get("kind"),
                "engine": "cv-nowcast-v1",
            }
        )
    return out, meta

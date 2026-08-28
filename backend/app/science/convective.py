"""Live cloudburst, downburst, and lightning nowcast from satellite + strokes.

Locked Open-Meteo hourly millimetres are never rewritten.
"""

from __future__ import annotations

from typing import Any

from app.data.physiography import classify
from app.science import sat_cv
from app.science.nowcast import _clip


def _level(score: int) -> str:
    if score >= 70:
        return "alert"
    if score >= 45:
        return "watch"
    return "quiet"


def _env(f: dict[str, Any]) -> dict[str, float]:
    from app.ml.features import value_at_now

    i = int(f.get("hourly_now_i") or 0)
    cape = value_at_now(f.get("hourly_cape") or [], i)
    gust = value_at_now(f.get("hourly_gust") or [], i)
    wind = value_at_now(f.get("hourly_wind") or [], i)
    rain1 = value_at_now(f.get("hourly_precip") or [], i)
    return {"cape": cape, "gust": gust, "wind": wind, "rain1": rain1}


def _pick_cell(cells: list[dict[str, Any]], lat: float, lon: float) -> dict[str, Any] | None:
    if not cells:
        return None
    best = cells[0]
    best_d = 1e9
    for c in cells:
        d = ((float(c["lat"]) - lat) ** 2 + (float(c["lon"]) - lon) ** 2) ** 0.5 * 111.3
        eta = sat_cv.pin_eta_min(c, lat, lon)
        score = d - (40 if eta is not None else 0) - (15 if c.get("ot") else 0)
        if score < best_d:
            best_d = score
            best = c
    return best


def build(
    f: dict[str, Any],
    loc: Any,
    live: dict[str, Any] | None = None,
    phys: dict[str, Any] | None = None,
) -> dict[str, Any]:
    live = live or {}
    lat = float(getattr(loc, "lat", 0) or 0)
    lon = float(getattr(loc, "lon", 0) or 0)
    phys = phys or classify(lat, lon, loc=loc, coast_km=f.get("coast_km"))
    env = _env(f)
    cells = list(live.get("cells") or [])
    strokes = list((live.get("lightning") or {}).get("strokes") or [])
    cell = _pick_cell(cells, lat, lon)
    eta = sat_cv.pin_eta_min(cell, lat, lon) if cell else None
    tb = None
    for src in (live.get("insat"), live.get("ir")):
        if src and src.get("tb_k") is not None:
            tb = float(src["tb_k"])
            break
    ir_mm = sat_cv.ir_rain_mmh(tb) if tb is not None else 0.0
    imerg = (live.get("imerg") or {}).get("mm_h")
    try:
        imerg_mm = float(imerg) if imerg is not None else None
    except (TypeError, ValueError):
        imerg_mm = None
    rain_sat = max(ir_mm, imerg_mm or 0.0)
    if cell:
        rain_sat = max(rain_sat, float(cell.get("rain_ir_mm_h") or 0))

    # --- lightning ---
    n_stroke = len(strokes)
    nearest = (live.get("lightning") or {}).get("nearest_km")
    jump = False
    if cell and (cell.get("trend") == "growing" or cell.get("ot")):
        jump = True
    l_score = 8
    if n_stroke:
        l_score += min(55, 18 + n_stroke * 8)
        if nearest is not None and float(nearest) <= 15:
            l_score += 20
        elif nearest is not None and float(nearest) <= 40:
            l_score += 10
    if jump:
        l_score += 16
    if env["cape"] >= 1500:
        l_score += 10
    elif env["cape"] >= 800:
        l_score += 5
    l_score = int(_clip(l_score, 0, 95))
    lightning = {
        "level": _level(l_score),
        "score_pct": l_score,
        "n_strokes": n_stroke,
        "nearest_km": nearest,
        "detected": bool(n_stroke),
        "nowcast": {
            "level": _level(l_score if jump or n_stroke else max(0, l_score - 20)),
            "eta_min": eta,
            "method": "stroke rate + IR lightning-jump",
        },
        "source": (live.get("lightning") or {}).get("source") or "none",
        "method": "weatherbit strokes + cell growth",
    }

    # --- cloudburst (extreme rain) ---
    cb = 6
    if cell and cell.get("min_tb_k") is not None and float(cell["min_tb_k"]) <= 221:
        cb += 22
    if cell and cell.get("ot"):
        cb += 12
    if rain_sat >= 20:
        cb += 22
    elif rain_sat >= 8:
        cb += 12
    if cell and cell.get("trend") == "growing":
        cb += 10
    if cell and float(cell.get("speed_kmh") or 99) < 18:
        cb += 10
    if eta is not None and eta <= 30:
        cb += 14
    elif eta is not None and eta <= 60:
        cb += 6
    if phys.get("kind") == "orographic":
        cb += 12
    if n_stroke >= 3:
        cb += 8
    cb = int(_clip(cb, 0, 95))
    cloudburst = {
        "level": _level(cb),
        "score_pct": cb,
        "eta_min": eta,
        "rain_ir_mm_h": round(ir_mm, 2),
        "rain_sat_mm_h": round(rain_sat, 2),
        "imerg_mm_h": imerg_mm,
        "cell_id": None if not cell else cell.get("id"),
        "orographic": phys.get("kind") == "orographic",
        "method": "IR cell + IMERG + stall + orography",
    }

    # --- downburst / microburst wind ---
    db = 6
    if cell and cell.get("trend") == "collapsing":
        db += 28
    if cell and (cell.get("d_tb_k") or 0) >= 2:
        db += 12
    if env["cape"] >= 1200:
        db += 16
    elif env["cape"] >= 700:
        db += 8
    shear = env["gust"] - env["wind"]
    if env["gust"] >= 50 and shear >= 22:
        db += 18
    elif env["gust"] >= 40:
        db += 8
    if rain_sat >= 10 or env["rain1"] >= 4:
        db += 8
    if eta is not None and eta <= 20:
        db += 10
    db = int(_clip(db, 0, 95))
    downburst = {
        "level": _level(db),
        "score_pct": db,
        "eta_min": eta,
        "gust_env_kmh": round(env["gust"], 1),
        "cape_jkg": round(env["cape"], 0),
        "cell_id": None if not cell else cell.get("id"),
        "method": "cell collapse + CAPE + gust shear",
    }

    track = sat_cv.forecast_track(cell) if cell else []
    return {
        "as_of": live.get("as_of"),
        "lightning": lightning,
        "cloudburst": cloudburst,
        "downburst": downburst,
        "cell": cell,
        "track": track,
        "n_cells": len(cells),
        "phys": phys.get("kind"),
        "sensors": {
            "insat": bool((live.get("insat") or {}).get("ok")),
            "gibs_ir": bool((live.get("ir") or {}).get("ok")),
            "imerg": bool((live.get("imerg") or {}).get("ok")),
            "lightning": bool((live.get("lightning") or {}).get("ok")),
        },
        "method": "live multi-sensor convective nowcast v1",
    }

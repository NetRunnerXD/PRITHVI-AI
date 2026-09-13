"""Fetch live satellite + lightning, run CV, persist tracks."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.config import ROOT
from app.science import sat_cv

TRACK_PATH = ROOT / ".cache" / "sat_tracks.json"


def _load_tracks() -> dict[str, Any]:
    if not TRACK_PATH.exists():
        return {}
    try:
        return json.loads(TRACK_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def _save_tracks(blob: dict[str, Any]) -> None:
    TRACK_PATH.parent.mkdir(parents=True, exist_ok=True)
    TRACK_PATH.write_text(json.dumps(blob, ensure_ascii=False), encoding="utf-8")


def place_key(loc: Any) -> str:
    lat = round(float(getattr(loc, "lat", 0) or 0), 3)
    lon = round(float(getattr(loc, "lon", 0) or 0), 3)
    name = getattr(loc, "place_name", None) or getattr(loc, "district", None) or "x"
    return f"{name}:{lat}:{lon}"


def _pick_grid(insat: dict[str, Any], ir: dict[str, Any]) -> tuple[list[list[float]] | None, float]:
    if insat.get("ok") and insat.get("grid"):
        return insat["grid"], 0.55
    if ir.get("ok") and ir.get("grid"):
        return ir["grid"], 1.1
    return None, 1.1


async def fetch(loc: Any) -> dict[str, Any]:
    import os

    if os.environ.get("PYTEST_CURRENT_TEST"):
        return {
            "ok": False,
            "status": "test-skip",
            "as_of": None,
            "insat": {"ok": False},
            "ir": {"ok": False},
            "imerg": {"ok": False},
            "channels": {"ok": False, "bands": []},
            "lightning": {"ok": False, "strokes": [], "n": 0},
            "cells": [],
            "method": "test-skip",
        }
    import asyncio

    from app import cache
    from app.providers import gibs_ir, gpm_imerg, imd_insat, weatherbit_lightning

    lat = float(getattr(loc, "lat", 0) or 0)
    lon = float(getattr(loc, "lon", 0) or 0)
    sat_key = f"sat_live:{round(lat, 2)}:{round(lon, 2)}"
    hit = cache.get(sat_key)
    if hit is not None and isinstance(hit, dict):
        return hit

    async def _safe(coro, default, timeout: float = 6.0):
        try:
            return await asyncio.wait_for(coro, timeout=timeout)
        except Exception:
            return default

    # IR1 + strokes first (must not share a 1.2 s deadline with five extra JPEGs).
    insat, lightning = await asyncio.gather(
        _safe(imd_insat.fetch_ir(lat, lon), {"ok": False}, 6.0),
        _safe(weatherbit_lightning.fetch(lat, lon), {"ok": False, "strokes": []}, 6.0),
    )
    ir, imerg, bands = await asyncio.gather(
        _safe(gibs_ir.fetch_ir(lat, lon), {"ok": False}, 4.0),
        _safe(gpm_imerg.fetch_pin(lat, lon, heavy=False), {}, 4.0),
        _safe(imd_insat.fetch_channels(lat, lon), {"ok": False, "bands": []}, 4.0),
    )
    grid, half = _pick_grid(insat, ir)
    try:
        from app.ml.vera.cv_branch import persist_grid

        persist_grid(grid, insat.get("url") or ir.get("url"))
        for b in (bands.get("bands") or []) if isinstance(bands, dict) else []:
            if isinstance(b, dict) and b.get("grid"):
                persist_grid(b.get("grid"), b.get("url"))
    except Exception:
        pass
    cells: list[dict[str, Any]] = []
    bounds = (lon - half, lon + half, lat - half, lat + half)
    if grid:
        cells = sat_cv.segment(grid, lat0=lat, lon0=lon, half_deg=half)
    key = place_key(loc)
    store = _load_tracks()
    prev_pack = store.get(key) or {}
    prev_cells = list(prev_pack.get("cells") or [])
    if not prev_cells:
        try:
            from app.science.cv_memory import last_ir_cells

            prev_cells = last_ir_cells()
        except Exception:
            prev_cells = []
    prev_t = prev_pack.get("t")
    dt_min = 10.0
    if prev_t:
        try:
            dt_min = max(4.0, (datetime.now(timezone.utc) - datetime.fromisoformat(str(prev_t).replace("Z", "+00:00"))).total_seconds() / 60.0)
        except ValueError:
            dt_min = 10.0
    if prev_cells and cells:
        cells = sat_cv.track(prev_cells, cells, dt_min)
    sat_cv.associate_strokes(cells, list(lightning.get("strokes") or []))
    try:
        from app.science import cv_nowcast

        cells, _cv = cv_nowcast.enhance(
            cells,
            grid,
            bounds,
            strokes=list(lightning.get("strokes") or []),
            bands=bands if isinstance(bands, dict) else None,
        )
    except Exception:
        pass
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    store[key] = {"t": now, "cells": cells}
    if len(store) > 80:
        store = dict(list(store.items())[-80:])
    try:
        _save_tracks(store)
    except OSError:
        pass
    out = {
        "as_of": now,
        "insat": {k: v for k, v in insat.items() if k != "grid"},
        "ir": {k: v for k, v in ir.items() if k != "grid"},
        "imerg": imerg,
        "lightning": lightning,
        "channels": bands,
        "cells": cells,
        "ok": bool(insat.get("ok") or ir.get("ok") or lightning.get("ok") or imerg.get("ok") or bands.get("ok")),
        "method": "imd-insat 5-band + gibs-ir/imerg + weatherbit",
    }
    sat_ok = bool(insat.get("ok") or ir.get("ok") or bands.get("ok"))
    cache.set(sat_key, out, 180 if sat_ok else 45)
    return out


def compact(live: dict[str, Any] | None) -> dict[str, Any]:
    live = live or {}
    return {
        "as_of": live.get("as_of"),
        "ok": live.get("ok"),
        "insat": live.get("insat"),
        "ir": live.get("ir"),
        "imerg": live.get("imerg"),
        "lightning": live.get("lightning"),
        "n_cells": len(live.get("cells") or []),
        "cells": (live.get("cells") or [])[:8],
        "method": live.get("method"),
    }

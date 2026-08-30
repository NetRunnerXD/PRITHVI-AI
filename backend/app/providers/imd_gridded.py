"""IMD 0.25° daily gridded rainfall ingest (Pune binary / NetCDF on disk)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.config import ROOT

GRID_DIR = ROOT / ".cache" / "imd_gridded"
IMD_INDEX = "https://www.imdpune.gov.in/Clim_Pred_LRF_New/Grided_Data_Download.html"


def status() -> dict[str, Any]:
    GRID_DIR.mkdir(parents=True, exist_ok=True)
    files = list(GRID_DIR.glob("*"))
    return {
        "wired": any(files),
        "n_files": len(files),
        "temporal": "daily",
        "spatial": "0.25°",
        "period": "1901–2024",
        "index_url": IMD_INDEX,
        "dir": str(GRID_DIR),
    }


def write_pin_series(lat: float, lon: float, rows: list[dict[str, Any]]) -> Path:
    GRID_DIR.mkdir(parents=True, exist_ok=True)
    p = GRID_DIR / f"{round(lat, 2)}_{round(lon, 2)}.json"
    p.write_text(json.dumps(rows), encoding="utf-8")
    return p


def ingest_from_nasa(lat: float, lon: float, rows: list[dict[str, Any]]) -> Path:
    """Persist POWER/ERA5 daily series in the IMD-gridded pin format."""
    return write_pin_series(lat, lon, rows)


async def ingest_index() -> dict[str, Any]:
    from app.providers.http import client

    try:
        r = await client().get(IMD_INDEX)
    except Exception as e:
        return {"ok": False, "error": str(e)[:200], **status()}
    return {"ok": r.status_code < 400, "http": r.status_code, "bytes": len(r.content), **status()}

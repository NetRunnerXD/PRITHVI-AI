"""Satellite frame *metadata* in Mongo. No HDF/JPEG/GridFS blobs.

Atlas M0 is 512 MB. Raw INSAT L1B is ~400 MB and IMERG HDF ~8 MB — never insert
those. Store granule id, times, and a sampled mm_h only.
"""

from __future__ import annotations

import io
import os
from typing import Any

from app.store import sat_mongo
from app.store.time import KEEP_MS, iso_z, ms, now_utc, parse_any

BUCKET = "sat_blobs"


def has_granule(granule_id: str) -> bool:
    if not granule_id:
        return False
    col = sat_mongo.col("sat_frames")
    if col is None:
        return False
    try:
        return col.find_one({"granule_id": str(granule_id)}, {"_id": 1}) is not None
    except Exception:
        return False


def put_frame(meta: dict[str, Any], grid: Any | None = None) -> dict[str, Any]:
    now = now_utc()
    started = parse_any(meta.get("started_at") or meta.get("started_ms")) or now
    frame_id = str(meta.get("frame_id") or f"{meta.get('source')}:{meta.get('product')}:{meta.get('granule_id')}")
    doc = {
        "frame_id": frame_id,
        "source": meta.get("source"),
        "product": meta.get("product"),
        "granule_id": str(meta.get("granule_id") or ""),
        "filename": meta.get("filename"),
        "started_at": iso_z(started),
        "started_ms": int(meta.get("started_ms") or ms(started)),
        "closes_at": meta.get("closes_at"),
        "closes_ms": meta.get("closes_ms"),
        "fetched_at": iso_z(now),
        "fetched_ms": ms(now),
        "bytes_raw": meta.get("bytes_raw"),
        "grid_kind": meta.get("grid_kind"),
        "grid_shape": meta.get("grid_shape"),
        "bounds": meta.get("bounds"),
        "quota_counted": bool(meta.get("quota_counted")),
        "status": meta.get("status") or "ok",
        "note": meta.get("note") or "metadata only — no imagery blob",
        "mm_h": meta.get("mm_h"),
    }
    col = sat_mongo.col("sat_frames")
    if col is None or os.environ.get("PYTEST_CURRENT_TEST"):
        return doc
    try:
        col.update_one({"frame_id": frame_id}, {"$set": doc}, upsert=True)
    except Exception:
        pass
    return doc


def load_grid(frame_id: str):
    col = sat_mongo.col("sat_frames")
    if col is None:
        return None
    try:
        doc = col.find_one({"frame_id": frame_id})
        if not doc or not doc.get("blob_id"):
            return None
        from gridfs import GridFS
        import numpy as np

        fs = GridFS(sat_mongo.db(), collection=BUCKET)
        raw = fs.get(doc["blob_id"]).read()
        return np.load(io.BytesIO(raw))["grid"]
    except Exception:
        return None


def latest(*, product: str | None = None, grid_kind: str | None = None) -> dict[str, Any] | None:
    col = sat_mongo.col("sat_frames")
    if col is None:
        return None
    q: dict[str, Any] = {}
    if product:
        q["product"] = product
    if grid_kind:
        q["grid_kind"] = grid_kind
    try:
        return col.find_one(q, {"_id": 0}, sort=[("started_ms", -1)])
    except Exception:
        return None


def prune() -> int:
    col = sat_mongo.col("sat_frames")
    if col is None:
        return 0
    cutoff = ms(now_utc()) - KEEP_MS
    n = 0
    try:
        old = list(col.find({"started_ms": {"$lt": cutoff}}))
        if not old:
            return 0
        ids = [d["_id"] for d in old]
        if ids:
            col.delete_many({"_id": {"$in": ids}})
            n = len(ids)
    except Exception:
        pass
    try:
        from app.config import ROOT

        for folder in (ROOT / ".cache" / "mosdac", ROOT / ".cache" / "imerg"):
            if not folder.exists():
                continue
            for p in folder.rglob("*"):
                if p.suffix.lower() in {".h5", ".hdf5", ".he5", ".HDF5"} and p.is_file():
                    p.unlink()
    except OSError:
        pass
    return n

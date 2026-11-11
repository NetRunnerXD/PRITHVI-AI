"""Storm-map and lightning packs written by the ingest service, read by the API.

The two Render Free processes do not share an in-memory cache. After an API
restart the in-process lightning cache is empty, which used to kick a global IR
mosaic and often OOM'd the instance. Ingest persists a slim pack here; the API
serves it and skips the heavy rebuild.
"""

from __future__ import annotations

import time
from typing import Any

STORM_ID = "india"
LTG_ID = "satltg:v1"
STORM_FRESH_S = 20 * 60
# How long the API may still draw a saved pack (with stale=true after FRESH).
# The old 6h cutoff blanked the map whenever ingest slept overnight.
STORM_SERVE_S = 48 * 3600
STORM_STALE_S = STORM_SERVE_S
LTG_FRESH_S = 20 * 60
LTG_SERVE_S = 48 * 3600
LTG_STALE_S = LTG_SERVE_S

_DROP = {"grid", "rgba", "body", "tb", "gray"}
_GEO_KEYS = (
    "cells",
    "incidents",
    "predicted",
    "predicted_storms",
    "predicted_unverified",
    "past_cells",
    "strokes",
    "past_strokes",
    "fires",
    "landslides",
    "polygons",
)


def _jsonable(obj: Any, depth: int = 0) -> Any:
    if depth > 8:
        return None
    if obj is None or isinstance(obj, (bool, int, float, str)):
        return obj
    if isinstance(obj, dict):
        out = {}
        for k, v in obj.items():
            key = str(k)
            if key in _DROP or key.startswith("_"):
                continue
            out[key] = _jsonable(v, depth + 1)
        return out
    if isinstance(obj, (list, tuple)):
        return [_jsonable(x, depth + 1) for x in obj]
    nbytes = getattr(obj, "nbytes", None)
    if isinstance(nbytes, (int, float)):
        # Large arrays stay out of Mongo; small ones (e.g. a 140×140 grid) may flatten.
        if int(nbytes) > 80_000:
            return None
        try:
            return obj.tolist()  # type: ignore[attr-defined]
        except Exception:
            return None
    item = getattr(obj, "item", None)
    if callable(item):
        try:
            return item()
        except Exception:
            return None
    return None


def slim_storm(pack: dict[str, Any] | None) -> dict[str, Any]:
    return _jsonable(pack or {}) or {}


def slim_lightning(pack: dict[str, Any] | None) -> dict[str, Any]:
    raw = _jsonable(pack or {}) or {}
    # Keep the cells the map needs; drop bulky validation hour tables on the wire.
    val = raw.get("validation")
    if isinstance(val, dict):
        raw["validation"] = {k: v for k, v in val.items() if k in {"total", "ok", "truth"} or k == "total"}
        if "hours" in val:
            raw["validation"].pop("hours", None)
    return raw


def _col(name: str):
    try:
        from app.store import sat_mongo

        return sat_mongo.col(name)
    except Exception:
        return None


def save_storm(pack: dict[str, Any] | None) -> bool:
    col = _col("storm_packs")
    if col is None or not pack:
        return False
    try:
        doc = slim_storm(pack)
        doc["saved_at"] = time.time()
        col.update_one({"_id": STORM_ID}, {"$set": doc}, upsert=True)
        return True
    except Exception:
        return False


def annotate_age(pack: dict[str, Any] | None, *, fresh_s: float = STORM_FRESH_S, kind: str = "storm") -> dict[str, Any] | None:
    """Mark a loaded pack stale when it is older than the fresh window, but keep it."""
    if not pack:
        return pack
    out = dict(pack)
    saved = float(out.get("saved_at") or 0)
    age = (time.time() - saved) if saved else None
    if age is None:
        return out
    out["ingest_age_s"] = int(age)
    if age > float(fresh_s):
        out["stale"] = True
        if not out.get("message"):
            out["message"] = f"Showing last saved {kind} pack (stale); ingest will refresh."
    else:
        out.setdefault("stale", False)
    return out


def load_storm(max_age_s: float = STORM_SERVE_S) -> dict[str, Any] | None:
    col = _col("storm_packs")
    if col is None:
        return None
    try:
        row = col.find_one({"_id": STORM_ID})
    except Exception:
        return None
    if not isinstance(row, dict):
        return None
    saved = float(row.get("saved_at") or 0)
    if saved and (time.time() - saved) > float(max_age_s):
        return None
    row.pop("_id", None)
    return annotate_age(row, fresh_s=STORM_FRESH_S, kind="storm")


def save_lightning(pack: dict[str, Any] | None) -> bool:
    col = _col("lightning_pack")
    if col is None or not pack:
        return False
    try:
        doc = slim_lightning(pack)
        doc["saved_at"] = time.time()
        col.update_one({"_id": LTG_ID}, {"$set": doc}, upsert=True)
        return True
    except Exception:
        return False


def load_lightning(max_age_s: float = LTG_SERVE_S) -> dict[str, Any] | None:
    col = _col("lightning_pack")
    if col is None:
        return None
    try:
        row = col.find_one({"_id": LTG_ID})
    except Exception:
        return None
    if not isinstance(row, dict):
        return None
    saved = float(row.get("saved_at") or 0)
    if saved and (time.time() - saved) > float(max_age_s):
        return None
    row.pop("_id", None)
    return annotate_age(row, fresh_s=LTG_FRESH_S, kind="lightning")


def crop_pack(pack: dict[str, Any], state: str, past_h: float | None = None) -> dict[str, Any]:
    """Filter an All-India ingest pack down to the requested state without rebuilding."""
    from app.data.india_districts import state_frame

    frame = state_frame(state)
    out = dict(pack)
    out["frame"] = frame
    out["state"] = frame.get("state") or state
    out["source"] = out.get("source") or "ingest-pack"
    if past_h is not None:
        out["past_h"] = past_h
    if frame.get("all_india"):
        return out

    def _ok(item: Any) -> bool:
        if not isinstance(item, dict):
            return False
        try:
            lat = float(item.get("lat") or item.get("latitude") or 0)
            lon = float(item.get("lon") or item.get("lng") or item.get("longitude") or 0)
        except (TypeError, ValueError):
            return False
        if not lat and not lon:
            return False
        try:
            from app.science.storm_map import _in_scope

            return _in_scope(lat, lon, frame)
        except Exception:
            south, north = frame.get("south", -90), frame.get("north", 90)
            west, east = frame.get("west", -180), frame.get("east", 180)
            return south <= lat <= north and west <= lon <= east

    for key in _GEO_KEYS:
        rows = out.get(key)
        if isinstance(rows, list):
            out[key] = [r for r in rows if _ok(r)]
    sl = out.get("sat_lightning")
    if isinstance(sl, dict) and isinstance(sl.get("cells"), list):
        sl = dict(sl)
        sl["cells"] = [r for r in sl["cells"] if _ok(r)]
        out["sat_lightning"] = sl
    return out

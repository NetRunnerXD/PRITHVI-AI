"""pn_runs — one compact document per live PN run (no grids, no blobs; ~1–2 KB each).

  _id/run_id "v7-2026102012"   issue hour (UTC) and model version
  t_issue_ms, run_at_ms        index: t_issue_ms
  status                       "model" | "persistence_fallback"
  groups {imerg,insat,gfs_rain,ifs_rain,gfs_env,ifs_env}   live (true) / masked (false)
  nwp {gfs:[runs], ifs:[runs], gfs_env, ifs_env}           NWP init times actually used
  verif {"1": {h,f,m,csi,pod,far,pc}, ..}                  0.5° scores per lead, filled in as the
                                                             observed IMERG hours arrive (pc = persistence CSI)
Size: 24 issue hours/day × ~1.7 KB ≈ 1.2 MB/month (+ index) — tiny next to the 512 MB M0 cap.
Mongo (MONGODB_SAT_URI via sat_mongo) when configured; otherwise memory + a small JSON file
under backend/.cache/ (git-ignored). Every failure is silent: the nowcast never depends on it.
"""

from __future__ import annotations

import json
import os
import threading
import time
from pathlib import Path
from typing import Any

from app.store import sat_mongo

COL = "pn_runs"
_lock = threading.Lock()
_MEM: dict[str, dict[str, Any]] = {}
_MAX_MEM = 2000
_indexed = False
_TRACK: dict[str, Any] = {}


def _disk() -> Path:
    return Path(os.environ.get("PN_RUNS_FILE") or Path(__file__).resolve().parents[2] / ".cache" / "pn_runs.json")


def _col():
    global _indexed
    try:
        c = sat_mongo.col(COL)
        if c is not None and not _indexed:
            c.create_index("t_issue_ms")
            _indexed = True
        return c
    except Exception:  # noqa: BLE001
        return None


def _save_disk() -> None:
    if os.environ.get("PYTEST_CURRENT_TEST") and not os.environ.get("PN_RUNS_FILE"):
        return
    try:
        p = _disk(); p.parent.mkdir(parents=True, exist_ok=True)
        tmp = p.with_suffix(".tmp")
        tmp.write_text(json.dumps(list(_MEM.values()), separators=(",", ":")), encoding="utf-8"); os.replace(tmp, p)
    except Exception:  # noqa: BLE001
        pass


def _load_disk() -> None:
    if _MEM:
        return
    try:
        p = _disk()
        if p.exists():
            for d in json.loads(p.read_text(encoding="utf-8")):
                _MEM[d["_id"]] = d
    except Exception:  # noqa: BLE001
        pass


def _r(v: float | None) -> float | None:
    return None if v is None else round(float(v), 3)


def scores(h: int, f: int, m: int) -> dict[str, Any]:
    return {"h": int(h), "f": int(f), "m": int(m), "csi": _r(h / (h + f + m)) if h + f + m else None,
            "pod": _r(h / (h + m)) if h + m else None, "far": _r(f / (h + f)) if h + f else None}


def upsert_run(doc: dict[str, Any]) -> None:
    """Insert/refresh the run header; keeps any verification already stored."""
    doc = {k: v for k, v in doc.items() if k != "verif"}
    doc["_id"] = doc["run_id"]
    with _lock:
        _load_disk()
        cur = _MEM.get(doc["_id"]) or {}
        _MEM[doc["_id"]] = {**cur, **doc, "verif": cur.get("verif") or {}}
        while len(_MEM) > _MAX_MEM:
            _MEM.pop(next(iter(_MEM)))
        _save_disk()
    c = _col()
    if c is not None:
        try:
            c.update_one({"_id": doc["_id"]}, {"$set": {k: v for k, v in doc.items() if k != "_id"}, "$setOnInsert": {"verif": {}}}, upsert=True)
        except Exception:  # noqa: BLE001
            pass


def add_verification(run_id: str, lead_h: int, s: dict[str, Any]) -> None:
    with _lock:
        _load_disk()
        d = _MEM.get(run_id)
        if d is not None:
            d.setdefault("verif", {})[str(lead_h)] = s
            _save_disk()
    c = _col()
    if c is not None:
        try:
            c.update_one({"_id": run_id}, {"$set": {f"verif.{lead_h}": s}})
        except Exception:  # noqa: BLE001
            pass


def verified_leads(run_id: str) -> set[int]:
    with _lock:
        _load_disk()
        return {int(k) for k in ((_MEM.get(run_id) or {}).get("verif") or {})}


def recent(days: float = 30) -> list[dict[str, Any]]:
    since = int((time.time() - days * 86400) * 1000)
    c = _col()
    if c is not None:
        try:
            return list(c.find({"t_issue_ms": {"$gte": since}}, {"_id": 0}).sort("t_issue_ms", 1).limit(5000))
        except Exception:  # noqa: BLE001
            pass
    with _lock:
        _load_disk()
        return sorted((dict(d) for d in _MEM.values() if int(d.get("t_issue_ms") or 0) >= since), key=lambda d: d["t_issue_ms"])


def track(days: float = 30, version: str | None = None) -> dict[str, Any]:
    """Live track record: pooled CSI/POD/FAR per lead (sum of counts) + persistence CSI, last `days`."""
    docs = [d for d in recent(days) if d.get("status") == "model" and (version is None or d.get("version") == version)]
    by: dict[int, list[int]] = {}; pc: dict[int, list[float]] = {}
    for d in docs:
        for k, v in (d.get("verif") or {}).items():
            a = by.setdefault(int(k), [0, 0, 0, 0]); a[0] += v.get("h", 0); a[1] += v.get("f", 0); a[2] += v.get("m", 0); a[3] += 1
            if v.get("pc") is not None: pc.setdefault(int(k), []).append(float(v["pc"]))
    leads = {str(L): {**scores(*by[L][:3]), "n_runs": by[L][3], "persistence_csi_mean": _r(sum(pc[L]) / len(pc[L])) if pc.get(L) else None} for L in sorted(by)}
    out = {"days": days, "n_runs": len(docs), "leads": leads, "scale_deg": 0.5, "event": "rain >= 1 mm/h", "as_of_ms": int(time.time() * 1000)}
    _TRACK.clear(); _TRACK.update(out)
    return out


def track_cached() -> dict[str, Any]:
    return dict(_TRACK)


def _reset_for_tests() -> None:
    global _indexed
    with _lock:
        _MEM.clear(); _TRACK.clear(); _indexed = False

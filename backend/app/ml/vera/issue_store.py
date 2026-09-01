"""Frozen forecast issues: MongoDB when configured, else JSONL via verify.LOG."""

from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any

from app.config import get_settings

_client = None


def mongo_ok() -> bool:
    if os.environ.get("PYTEST_CURRENT_TEST"):
        return False
    return bool((get_settings().mongodb_uri or "").strip())


def _col():
    global _client
    if not mongo_ok():
        return None
    if _client is None:
        from pymongo import MongoClient

        _client = MongoClient(get_settings().mongodb_uri.strip(), serverSelectionTimeoutMS=8000)
        db = _client[get_settings().mongodb_db or "rituchakra"]
        db.forecast_issues.create_index([("pin", 1), ("valid_at", 1), ("lead_h", 1)], unique=True)
    return _client[get_settings().mongodb_db or "rituchakra"].forecast_issues


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def upsert_frozen(rows: list[dict[str, Any]]) -> None:
    col = _col()
    if col is None:
        return
    for r in rows:
        pin = r.get("pin")
        valid = str(r.get("t") or "")[:16]
        lead = int(r.get("lead_h") or 0)
        if not pin or not valid:
            continue
        doc = {
            "pin": pin,
            "valid_at": valid,
            "lead_h": lead,
            "issued_at": r.get("issued_at") or _now(),
            "blend": r.get("moe"),
            "ensemble": r.get("ensemble"),
            "members": r.get("members") or {},
            "om_issued": r.get("om_issued", r.get("om")),
            "vars": {"precip_mm": r.get("moe")},
        }
        try:
            col.update_one(
                {"pin": pin, "valid_at": valid, "lead_h": lead},
                {"$setOnInsert": doc},
                upsert=True,
            )
        except Exception:
            continue


def set_obs(pin: str, valid_at: str, lead_h: int | None, obs: float, source: str) -> None:
    col = _col()
    if col is None:
        return
    q: dict[str, Any] = {"pin": pin, "valid_at": {"$regex": f"^{str(valid_at)[:13]}"}}
    if lead_h is not None:
        q["lead_h"] = int(lead_h)
    try:
        col.update_many(
            {**q, "$or": [{"obs": None}, {"obs": {"$exists": False}}]},
            {"$set": {"obs": float(obs), "obs_source": source, "obs_at": _now()}},
        )
    except Exception:
        return


def load_pin(pin: str, limit: int = 400) -> list[dict[str, Any]] | None:
    col = _col()
    if col is None:
        return None
    try:
        cur = col.find({"pin": pin}).sort("valid_at", -1).limit(limit)
        out = []
        for d in cur:
            out.append(
                {
                    "pin": d.get("pin"),
                    "t": d.get("valid_at"),
                    "lead_h": d.get("lead_h"),
                    "issued_at": d.get("issued_at"),
                    "ensemble": d.get("ensemble"),
                    "moe": d.get("blend"),
                    "om": d.get("om_issued"),
                    "om_issued": d.get("om_issued"),
                    "members": d.get("members") or {},
                    "obs": d.get("obs"),
                    "obs_source": d.get("obs_source"),
                }
            )
        out.reverse()
        return out
    except Exception:
        return None

"""MongoDB Atlas when MONGODB_URI is set; otherwise an in-process store."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from app.config import get_settings

_memory_users: dict[str, dict[str, Any]] = {}
_memory_sms: list[dict[str, Any]] = []
_motor_client = None
_motor_db = None


def reset_memory() -> None:
    _memory_users.clear()
    _memory_sms.clear()


def mongo_enabled() -> bool:
    return bool((get_settings().mongodb_uri or "").strip())


async def connect() -> None:
    global _motor_client, _motor_db
    uri = (get_settings().mongodb_uri or "").strip()
    if not uri:
        return
    from motor.motor_asyncio import AsyncIOMotorClient

    _motor_client = AsyncIOMotorClient(uri)
    _motor_db = _motor_client[get_settings().mongodb_db or "rituchakra"]
    await _motor_db.users.create_index("phone", unique=True)
    await _motor_db.forecast_issues.create_index([("pin", 1), ("valid_at", 1), ("lead_h", 1)], unique=True)


async def close() -> None:
    global _motor_client, _motor_db
    if _motor_client is not None:
        _motor_client.close()
    _motor_client = None
    _motor_db = None


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def public_user(doc: dict[str, Any]) -> dict[str, Any]:
    loc = doc.get("location") or {}
    return {
        "id": doc["_id"],
        "phone": doc["phone"],
        "display_name": doc.get("display_name") or "",
        "email": doc.get("email") or None,
        "sms_opt_in": bool(doc.get("sms_opt_in")),
        "location": {
            "lat": loc.get("lat"),
            "lon": loc.get("lon"),
            "place": loc.get("place"),
            "district": loc.get("district"),
            "state": loc.get("state"),
            "captured_at": loc.get("captured_at"),
            "source": loc.get("source"),
        }
        if loc.get("lat") is not None
        else None,
        "created_at": doc.get("created_at"),
        "updated_at": doc.get("updated_at"),
    }


async def insert_user(doc: dict[str, Any]) -> dict[str, Any]:
    doc = dict(doc)
    doc.setdefault("_id", str(uuid4()))
    doc.setdefault("created_at", _now())
    doc["updated_at"] = _now()
    if _motor_db is not None:
        await _motor_db.users.insert_one(doc)
        return doc
    if any(u["phone"] == doc["phone"] for u in _memory_users.values()):
        raise ValueError("phone_taken")
    _memory_users[doc["_id"]] = doc
    return doc


async def find_by_phone(phone: str) -> dict[str, Any] | None:
    if _motor_db is not None:
        return await _motor_db.users.find_one({"phone": phone})
    for u in _memory_users.values():
        if u["phone"] == phone:
            return u
    return None


async def find_by_id(uid: str) -> dict[str, Any] | None:
    if _motor_db is not None:
        return await _motor_db.users.find_one({"_id": uid})
    return _memory_users.get(uid)


async def update_user(uid: str, patch: dict[str, Any]) -> dict[str, Any] | None:
    patch = {k: v for k, v in patch.items() if v is not None or k in {"email", "reset"}}
    patch["updated_at"] = _now()
    if _motor_db is not None:
        await _motor_db.users.update_one({"_id": uid}, {"$set": patch})
        return await find_by_id(uid)
    cur = _memory_users.get(uid)
    if not cur:
        return None
    cur.update(patch)
    return cur


async def opted_in_users() -> list[dict[str, Any]]:
    if _motor_db is not None:
        cur = _motor_db.users.find({"sms_opt_in": True})
        return await cur.to_list(length=500)
    return [u for u in _memory_users.values() if u.get("sms_opt_in")]


async def sms_already_sent(user_id: str, fingerprint: str) -> bool:
    if _motor_db is not None:
        row = await _motor_db.sms_log.find_one({"user_id": user_id, "fingerprint": fingerprint})
        return row is not None
    return any(r["user_id"] == user_id and r["fingerprint"] == fingerprint for r in _memory_sms)


async def log_sms(user_id: str, fingerprint: str, body: str) -> None:
    row = {"user_id": user_id, "fingerprint": fingerprint, "body": body, "sent_at": _now()}
    if _motor_db is not None:
        await _motor_db.sms_log.insert_one(row)
        return
    _memory_sms.append(row)

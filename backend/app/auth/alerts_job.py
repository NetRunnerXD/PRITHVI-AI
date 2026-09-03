"""SMS alerts for opted-in users at their logged India location."""

from __future__ import annotations

import asyncio
import hashlib
import logging
import os

from app.auth import db
from app.auth.sms import send_sms
from app.config import get_settings
from app.services.location_svc import resolve_location
from app.services.snapshot import build_snapshot

log = logging.getLogger("rituchakra.sms_alerts")

SEVERE = {"extreme", "warning"}


def _fp(user_id: str, title: str, kind: str) -> str:
    raw = f"{user_id}|{kind}|{title}".encode("utf-8")
    return hashlib.sha256(raw).hexdigest()[:32]


def _sms_text(place: str, title: str, kind: str) -> str:
    head = f"Rituchakra {kind or 'alert'} @ {place}: {title}"
    return head[:160]


async def scan_once() -> int:
    sent = 0
    users = await db.opted_in_users()
    for user in users:
        locd = user.get("location") or {}
        if locd.get("lat") is None or locd.get("lon") is None:
            continue
        loc = resolve_location(
            q=locd.get("place") or locd.get("district"),
            lat=float(locd["lat"]),
            lon=float(locd["lon"]),
        )
        try:
            snap = await build_snapshot(loc)
        except Exception:
            log.exception("sms snapshot failed for %s", user.get("_id"))
            continue
        place = loc.place_name or loc.district
        warnings = (
            getattr(snap, "warnings", None)
            or (snap.prescriptive.warnings if getattr(snap, "prescriptive", None) else [])
        )
        for w in warnings or []:
            if (w.severity or "").lower() not in SEVERE:
                continue
            fp = _fp(user["_id"], w.title, w.kind or w.hazard or "")
            if await db.sms_already_sent(user["_id"], fp):
                continue
            text = _sms_text(place, w.title, w.kind or w.hazard or "alert")
            await send_sms(user["phone"], text)
            await db.log_sms(user["_id"], fp, text)
            sent += 1
    return sent


async def loop() -> None:
    s = get_settings()
    wait = max(120.0, float(s.sms_alert_interval_s or 900))
    await asyncio.sleep(60)
    while True:
        try:
            await scan_once()
        except Exception:
            log.exception("sms alert scan")
        await asyncio.sleep(wait)


def should_start() -> bool:
    if os.environ.get("PYTEST_CURRENT_TEST") or os.environ.get("RITUCHAKRA_NO_SNAP_LOOP"):
        return False
    return True

from __future__ import annotations

import logging

from app.config import get_settings
from app.providers.http import client

log = logging.getLogger("rituchakra.sms")

FAST2SMS = "https://www.fast2sms.com/dev/bulkV2"


def _digits_in(phone: str) -> str:
    d = "".join(c for c in phone if c.isdigit())
    if d.startswith("91") and len(d) == 12:
        return d[2:]
    return d[-10:]


async def send_sms(phone: str, message: str) -> dict:
    s = get_settings()
    numbers = _digits_in(phone)
    payload = {"phone": numbers, "message": message[:160]}
    if s.sms_dry_run or not (s.fast2sms_api_key or "").strip():
        log.info("sms dry-run %s %s", numbers, message[:160])
        return {"ok": True, "dry_run": True, **payload}
    r = await client().post(
        FAST2SMS,
        headers={"authorization": s.fast2sms_api_key.strip()},
        data={
            "route": "q",
            "message": message[:160],
            "language": "english",
            "flash": "0",
            "numbers": numbers,
        },
    )
    try:
        body = r.json()
    except Exception:
        body = {"text": r.text[:200]}
    ok = r.status_code < 400 and bool(body.get("return", True))
    return {"ok": ok, "dry_run": False, "status": r.status_code, "provider": body}

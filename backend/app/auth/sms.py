from __future__ import annotations

import logging

import httpx

from app.config import get_settings

log = logging.getLogger("rituchakra.sms")

FAST2SMS = "https://www.fast2sms.com/dev/bulkV2"
QUICK_ROUTE = "q"
SMS_MAX = 160


def _digits_in(phone: str) -> str:
    d = "".join(c for c in phone if c.isdigit())
    if d.startswith("91") and len(d) == 12:
        return d[2:]
    return d[-10:] if len(d) >= 10 else d


def demo_phone() -> str:
    s = get_settings()
    return _digits_in(s.sms_demo_to or "7439972482") or "7439972482"


def status() -> dict:
    s = get_settings()
    key = (s.fast2sms_api_key or "").strip()
    return {
        "provider": "fast2sms",
        "route": "q",
        "endpoint": FAST2SMS,
        "enabled": bool(s.sms_enabled),
        "dry_run": bool(s.sms_dry_run),
        "has_key": bool(key),
        "live": bool(s.sms_enabled and not s.sms_dry_run and key),
        "demo_to": f"+91 {demo_phone()}",
        "note": "Background alerts stay off unless SMS_ENABLED=true and SMS_DRY_RUN=false.",
    }


async def send_sms(phone: str, message: str, *, force: bool = False) -> dict:
    """Quick SMS (route=q). Default is dry-run. force=True is the Settings demo send."""
    s = get_settings()
    numbers = _digits_in(phone)
    text = (message or "")[:SMS_MAX]
    payload = {"phone": numbers, "message": text, "route": QUICK_ROUTE}
    key = (s.fast2sms_api_key or "").strip()
    if force:
        if not numbers or len(numbers) != 10:
            return {"ok": False, "dry_run": False, "error": "invalid_indian_mobile", **payload}
        if not key:
            return {"ok": False, "dry_run": True, "error": "missing_fast2sms_key", **payload}
        return await _quick_sms(key, numbers, text, payload)
    if (not s.sms_enabled) or s.sms_dry_run or not key:
        log.info("sms dry-run %s %s", numbers, text)
        return {"ok": True, "dry_run": True, **payload}
    return await _quick_sms(key, numbers, text, payload)


async def _quick_sms(key: str, numbers: str, text: str, payload: dict) -> dict:
    headers = {"authorization": key}
    params = {
        "route": QUICK_ROUTE,
        "message": text,
        "language": "english",
        "flash": "0",
        "numbers": numbers,
    }
    timeout = httpx.Timeout(20.0, connect=8.0)
    try:
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as http:
            r = await http.post(FAST2SMS, headers=headers, data=params)
            if r.status_code >= 400:
                r = await http.get(
                    FAST2SMS,
                    headers=headers,
                    params={"authorization": key, **params},
                )
    except httpx.HTTPError as exc:
        log.exception("fast2sms quicksms failed")
        return {"ok": False, "dry_run": False, "error": str(exc)[:200], **payload}
    try:
        body = r.json()
    except Exception:
        body = {"text": (r.text or "")[:200]}
    returned = body.get("return") if isinstance(body, dict) else None
    ok = r.status_code < 400 and (returned is True or returned is None)
    if isinstance(returned, bool):
        ok = r.status_code < 400 and returned
    return {
        "ok": ok,
        "dry_run": False,
        "status": r.status_code,
        "provider": body,
        **payload,
    }

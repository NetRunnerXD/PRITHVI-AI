"""HTTP-kick the dedicated ingest service when packs or status are stale.

Render Free has no native cron. While the site has visitors the API triggers
at most once per 10 minutes. An external uptime pinger is still useful to
keep both free services warm when nobody is around at the IST half-hour slot.
"""

from __future__ import annotations

import asyncio
import logging
import os
import time
from typing import Any

log = logging.getLogger("app.ingest.kick")

THROTTLE_S = 10 * 60
_lock = asyncio.Lock()
_last_mono = 0.0


def ingest_base_url() -> str:
    from app.config import get_settings

    s = get_settings()
    return (os.environ.get("INGEST_BASE_URL") or (s.ingest_base_url or "")).strip().rstrip("/")


def reset_throttle() -> None:
    """Test helper."""
    global _last_mono
    _last_mono = 0.0


def pack_or_status_stale() -> bool:
    """True when the API should ask ingest to run a cycle."""
    try:
        from app.store import ingest_status
        from app.store import shared_packs

        saved = shared_packs.storm_saved_at()
        if not saved or (time.time() - saved) > float(shared_packs.STORM_FRESH_S):
            return True
        snap = ingest_status.snapshot()
        return bool(snap.get("stale"))
    except Exception:
        return True


_ready_probe_mono = 0.0
READY_PROBE_S = 60.0


async def ready_probe(reason: str = "ready-stale") -> None:
    """Background staleness probe for /api/ready: the Mongo read runs in a thread and at
    most once a minute, so the health check itself never waits on it."""
    global _ready_probe_mono
    now = time.monotonic()
    if _ready_probe_mono and (now - _ready_probe_mono) < READY_PROBE_S:
        return
    _ready_probe_mono = now
    try:
        stale = await asyncio.to_thread(pack_or_status_stale)
    except Exception:
        return
    if stale:
        try:
            await kick_if_stale(reason)
        except Exception:
            pass


def build_kick_request(base: str, secret: str = "") -> tuple[str, dict[str, str]]:
    params = {"background": "true"}
    if secret:
        params["secret"] = secret
    return f"{base.rstrip('/')}/api/ingest/trigger", params


def should_throttle(last_mono: float, now_mono: float, window: float = THROTTLE_S) -> bool:
    return bool(last_mono and (now_mono - last_mono) < window)


async def kick_if_stale(reason: str = "stale") -> dict[str, Any]:
    """POST /api/ingest/trigger on the ingest host. No-ops when throttled or unconfigured.

    Sends INGEST_CRON_SECRET as `secret` when the API has one set.
    """
    global _last_mono
    if os.environ.get("PYTEST_CURRENT_TEST"):
        return {"ok": False, "status": "pytest"}
    base = ingest_base_url()
    if not base:
        return {"ok": False, "status": "no_ingest_url"}
    async with _lock:
        now = time.monotonic()
        if _last_mono and (now - _last_mono) < THROTTLE_S:
            return {"ok": False, "status": "throttled"}
        _last_mono = now
    from app.config import get_settings

    secret = (get_settings().ingest_cron_secret or "").strip()
    url, params = build_kick_request(base, secret)
    try:
        import httpx

        async with httpx.AsyncClient(timeout=5.0, follow_redirects=True) as client:
            r = await client.post(url, params=params)
        log.info("ingest kick reason=%s status=%s", reason, r.status_code)
        return {"ok": r.status_code < 400, "status": int(r.status_code)}
    except Exception as exc:
        log.warning("ingest kick failed reason=%s err=%s", reason, type(exc).__name__)
        return {"ok": False, "status": "error"}

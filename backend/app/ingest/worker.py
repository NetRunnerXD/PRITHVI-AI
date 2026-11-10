"""Loop satellite ingest. `python -m app.ingest.worker` or APP_ROLE=ingest.

Cycles run on IST half-hours (00:00, 00:30, …). A restart downloads the current
slot only when that slot has no saved frame.
"""

from __future__ import annotations

import asyncio
import logging
import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

from app.config import get_settings

log = logging.getLogger("app.ingest")

IST = timezone(timedelta(hours=5, minutes=30))


def interval_s() -> float:
    try:
        return max(60.0, float(os.environ.get("INGEST_INTERVAL_S") or 180))
    except ValueError:
        return 180.0


def slot_bounds(now: datetime) -> tuple[str, datetime, datetime, datetime]:
    """Current IST half-hour: key, start, next start, retry (start+10min)."""
    ist = now.astimezone(IST)
    start = ist.replace(minute=0 if ist.minute < 30 else 30, second=0, microsecond=0)
    nxt = start + timedelta(minutes=30)
    retry = start + timedelta(minutes=10)
    return start.strftime("%Y-%m-%dT%H%M"), start, nxt, retry


def seconds_until(now: datetime, target: datetime) -> float:
    return max(0.0, (target.astimezone(timezone.utc) - now.astimezone(timezone.utc)).total_seconds())


def slot_dir() -> Path | None:
    if os.environ.get("PYTEST_CURRENT_TEST") and not os.environ.get("INGEST_SLOT_DIR"):
        return None
    override = os.environ.get("INGEST_SLOT_DIR")
    if override:
        return Path(override)
    return get_settings().cache_dir / "ingest_slots"


def slot_has_frame(key: str) -> bool:
    root = slot_dir()
    if root is None:
        return False
    return (root / f"{key}.json").is_file()


def _in_slot(raw, start: datetime, end: datetime) -> bool:
    from app.store.time import parse_any

    t = parse_any(raw)
    if t is None:
        return False
    return start <= t.astimezone(IST) < end


def record_slot_frame(*, jpeg_time=None, hem_time=None, now: datetime | None = None) -> bool:
    """Close the current slot only when a product time falls inside it."""
    root = slot_dir()
    if root is None:
        return False
    now = now or datetime.now(timezone.utc)
    key, start, end, _retry = slot_bounds(now)
    products = {}
    if _in_slot(jpeg_time, start, end):
        products["jpeg"] = jpeg_time
    if _in_slot(hem_time, start, end):
        products["hem"] = hem_time
    if not products:
        return False
    root.mkdir(parents=True, exist_ok=True)
    (root / f"{key}.json").write_text(
        json.dumps(
            {
                "slot_ist": key,
                "products": products,
                "ok": True,
                "downloaded_at": datetime.now(timezone.utc).isoformat(),
            }
        ),
        encoding="utf-8",
    )
    return True


def due_token(now: datetime, attempted: set[str], *, is_stale: bool = False) -> str | None:
    """One opening attempt before slot+10min, one retry after, while the slot file is missing.

    When ``is_stale`` is true (no fresh shared pack / empty ingest status), a
    restart still runs the current slot even if a slot file already exists —
    the file only means a frame was downloaded, not that packs were published.
    """
    key, _start, _nxt, retry = slot_bounds(now)
    if slot_has_frame(key) and not is_stale:
        return None
    token = key if now.astimezone(IST) < retry else f"{key}:retry"
    if is_stale and token in attempted:
        token = f"{key}:stale"
    if token in attempted:
        return None
    return token


def sleep_s(now: datetime, attempted: set[str]) -> float:
    key, _start, nxt, retry = slot_bounds(now)
    targets = [nxt]
    if (
        not slot_has_frame(key)
        and now.astimezone(IST) < retry
        and key in attempted
        and f"{key}:retry" not in attempted
    ):
        targets.append(retry)
    return max(1.0, min(seconds_until(now, t) for t in targets))


def _status_stale() -> bool:
    """True when this process has no usable cycle or the shared storm pack is missing/old."""
    try:
        from app.store import ingest_status
        from app.store import shared_packs

        snap = ingest_status.snapshot()
        if not snap.get("cycle_id") or snap.get("stale") or snap.get("phase") in {"idle", "error"}:
            return True
        pack = shared_packs.load_storm(max_age_s=shared_packs.STORM_FRESH_S)
        return pack is None
    except Exception:
        return True


async def _clock_loop() -> None:
    from app.ingest.cycle import run_cycle

    attempted: set[str] = set()
    boot = True
    while True:
        now = datetime.now(timezone.utc)
        stale = _status_stale()
        token = due_token(now, attempted, is_stale=stale or boot)
        if token:
            try:
                log.info("ingest cycle start token=%s stale=%s boot=%s", token, stale, boot)
                result = await run_cycle()
                log.info(
                    "ingest cycle finish token=%s ok=%s cycle_id=%s",
                    token,
                    (result or {}).get("ok"),
                    (result or {}).get("cycle_id"),
                )
            except Exception:
                log.exception("ingest cycle failed token=%s", token)
            attempted.add(token)
        boot = False
        delay = sleep_s(datetime.now(timezone.utc), attempted)
        if stale and delay > 10 * 60:
            # Don't wait a full half-hour to republish a missing pack.
            delay = 10 * 60.0
        await asyncio.sleep(delay)


async def ingest_loop() -> None:
    await _clock_loop()


def embedded_mode() -> str:
    """INGEST_EMBEDDED: 'auto' (default) = run cycles in the API process only while no
    dedicated worker keeps the shared status fresh; '1' = always; '0' = never.

    Auto turns off when INGEST_BASE_URL is set or the API is running in
    CLOUD_LIGHT/Render — those hosts must not rebuild IR in-process.
    """
    v = (os.environ.get("INGEST_EMBEDDED") or "auto").strip().lower()
    if v in {"0", "false", "no", "off"}:
        return "off"
    if v in {"1", "true", "yes", "on", "always"}:
        return "on"
    try:
        from app.ingest.kick import ingest_base_url

        if ingest_base_url():
            return "off"
    except Exception:
        pass
    try:
        from app.config import cloud_light

        role = (get_settings().app_role or "api").strip().lower()
        if cloud_light() and role != "ingest":
            return "off"
    except Exception:
        pass
    return "auto"


async def embedded_loop() -> None:
    """IST half-hour ingest for single-service deploys. A restart fetches the current
    slot only when its frame file is missing."""
    if embedded_mode() == "off":
        return
    await _clock_loop()


def main() -> None:
    os.environ.setdefault("APP_ROLE", "ingest")
    asyncio.run(_main())


async def _main() -> None:
    s = get_settings()
    if s.sat_wipe_confirm:
        from app.store.sat_mongo import wipe_user_databases

        print(wipe_user_databases())
    await ingest_loop()


if __name__ == "__main__":
    main()

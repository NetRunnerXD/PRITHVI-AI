"""Loop satellite ingest. `python -m app.ingest.worker` or APP_ROLE=ingest.

Cycles run on IST half-hours (00:00, 00:30, …). A restart downloads the current
slot only when that slot has no saved frame.
"""

from __future__ import annotations

import asyncio
import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

from app.config import get_settings

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


def due_token(now: datetime, attempted: set[str]) -> str | None:
    """One opening attempt before slot+10min, one retry after, while the slot file is missing."""
    key, _start, _nxt, retry = slot_bounds(now)
    if slot_has_frame(key):
        return None
    token = key if now.astimezone(IST) < retry else f"{key}:retry"
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


async def _clock_loop() -> None:
    from app.ingest.cycle import run_cycle

    attempted: set[str] = set()
    while True:
        now = datetime.now(timezone.utc)
        token = due_token(now, attempted)
        if token:
            try:
                await run_cycle()
            except Exception:
                pass
            attempted.add(token)
        await asyncio.sleep(sleep_s(datetime.now(timezone.utc), attempted))


async def ingest_loop() -> None:
    await _clock_loop()


def embedded_mode() -> str:
    """INGEST_EMBEDDED: 'auto' (default) = run cycles in the API process only while no
    dedicated worker keeps the shared status fresh; '1' = always; '0' = never."""
    v = (os.environ.get("INGEST_EMBEDDED") or "auto").strip().lower()
    if v in {"0", "false", "no", "off"}:
        return "off"
    if v in {"1", "true", "yes", "on", "always"}:
        return "on"
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

"""Loop satellite ingest. `python -m app.ingest.worker` or APP_ROLE=ingest."""

from __future__ import annotations

import asyncio
import os

from app.config import get_settings


def interval_s() -> float:
    try:
        return max(60.0, float(os.environ.get("INGEST_INTERVAL_S") or 180))
    except ValueError:
        return 180.0


async def ingest_loop() -> None:
    from app.ingest.cycle import run_cycle

    wait = interval_s()
    await asyncio.sleep(8)
    while True:
        try:
            await run_cycle()
        except Exception:
            pass
        await asyncio.sleep(wait)


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
    """Self-healing ingest for single-service deploys (Render free web service, the laptop).
    Previously the API never ingested, so the shared status and the past-event ledger froze
    at the last time a worker ran (168 h on 2026-10-20)."""
    from app.ingest.cycle import run_cycle
    from app.store import ingest_status

    wait = interval_s()
    mode = embedded_mode()
    await asyncio.sleep(float(os.environ.get("INGEST_EMBEDDED_DELAY_S") or 20))
    while True:
        try:
            run = mode == "on"
            if mode == "auto":
                snap = ingest_status.snapshot()
                age = snap.get("age_s")
                busy = snap.get("phase") in {"fetching", "cv", "predict", "alerts"} and age is not None and age < 900
                run = (age is None or age > 2 * wait + 60) and not busy
            if run:
                await run_cycle()
        except Exception:
            pass
        await asyncio.sleep(wait)


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

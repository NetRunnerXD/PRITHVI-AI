"""Loop satellite ingest. `python -m app.ingest.worker` or APP_ROLE=ingest."""

from __future__ import annotations

import asyncio
import os

from app.config import get_settings


async def ingest_loop() -> None:
    from app.ingest.cycle import run_cycle

    wait = 180.0
    await asyncio.sleep(8)
    while True:
        try:
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

"""Background prefetch: keep the expensive shared upstream data warm so user requests are
served from cache. Runs inside the API process (lifespan). Disable with PREFETCH_ENABLED=0.

Quota-safe: every job goes through the same caches as user requests (Open-Meteo storm
batch is cached 600 s, so prefetch never adds more than one batch per 10 min).
"""

from __future__ import annotations

import asyncio
import logging
import os
import random
import time

log = logging.getLogger("prithvi.prefetch")

# (name, period_s)
JOBS: tuple[tuple[str, float], ...] = (
    ("insat", 120.0),
    ("gibs", 600.0),
    ("storm_india", 90.0),
    ("cyclones", 600.0),
    ("sachet_india", 600.0),
    ("sachet_states", 1800.0),
    ("default_pin", 540.0),
)


async def _run(name: str) -> None:
    if name == "insat":
        from app.providers import imd_insat

        await imd_insat.fetch_sector()
        await imd_insat.map_area()
    elif name == "gibs":
        from app.providers import gibs_ir

        await asyncio.gather(gibs_ir.frame("ir"), gibs_ir.frame("imerg"))
    elif name == "storm_india":
        from app import cache
        from app.science.storm_map import build
        from app.store.time import clamp_horizon

        h = clamp_horizon(6)
        await cache.aget(f"stormpack:india:{h}", lambda: build("India", past_h=h), ttl_s=90, swr_s=600)
    elif name == "cyclones":
        from app.providers import cyclones

        await cyclones.active("india")
    elif name == "sachet_india":
        from app.providers import sachet

        await sachet.alerts(None)
    elif name == "default_pin":
        # First-time visitors now get the server default city immediately (no GPS wait),
        # so keep that one snapshot warm (one Open-Meteo pin per ~9 min).
        from app.config import get_settings
        from app.services.location_svc import resolve_location
        from app.services.snapshot import build_snapshot

        st = get_settings()
        await build_snapshot(resolve_location(lat=float(st.default_lat), lon=float(st.default_lon)))
    elif name == "sachet_states":
        from app.providers import sachet

        await sachet.warm_all_states()


async def prefetch_loop() -> None:
    await asyncio.sleep(float(os.environ.get("PREFETCH_DELAY_S") or 20))
    due = {name: 0.0 for name, _ in JOBS}
    period = dict(JOBS)
    while True:
        now = time.monotonic()
        for name in list(due):
            if now < due[name]:
                continue
            due[name] = now + period[name] * (0.9 + 0.2 * random.random())
            try:
                await asyncio.wait_for(_run(name), timeout=60.0)
            except asyncio.CancelledError:
                raise
            except Exception as e:  # never kill the loop
                log.warning("prefetch %s failed: %s", name, type(e).__name__)
        await asyncio.sleep(5.0)

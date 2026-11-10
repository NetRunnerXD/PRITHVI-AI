from unittest.mock import AsyncMock, patch

import pytest

from app.config import get_settings
from app.ingest.cycle import run_cycle


def _l1b_off():
    s = get_settings()
    prev = s.mosdac_allow_l1b
    s.mosdac_allow_l1b = False
    return s, prev


@pytest.mark.asyncio
async def test_cycle_always_fetches_insat_jpeg():
    jpeg = AsyncMock(return_value={"body": b"jpeg-bytes", "url": "http://imd", "status": "ok", "image_time": None})
    mosdac = AsyncMock(return_value=[{"ok": True, "product": "3SIMG_L2B_HEM", "cached": True}])
    imerg = AsyncMock(return_value={"ok": True})
    pack = {
        "ok": True,
        "counts": {"predicted": 1},
        "sensors": {"gibs_ir": True},
        "need_second_frame": True,
        "incidents": [],
    }
    settings, prev = _l1b_off()
    try:
        with (
            patch("app.providers.imd_insat.fetch_frame", jpeg),
            patch("app.providers.mosdac.ingest_latest", mosdac),
            patch("app.providers.gpm_imerg.fetch_pin", imerg),
            patch("app.science.storm_map.build", AsyncMock(return_value=pack)),
            patch("app.science.sat_lightning.refresh", AsyncMock(return_value={"ok": True, "cells": []})),
        ):
            out = await run_cycle()
    finally:
        settings.mosdac_allow_l1b = prev
    jpeg.assert_awaited()
    assert out["ok"] is True
    from app.store.ingest_status import snapshot

    snap = snapshot()
    assert snap["ready"] is True
    by_id = {s["id"]: s for s in snap["satellites"]}
    assert by_id["mosdac_hem"]["status"] == "ok"
    assert by_id["mosdac_l1b"]["status"] == "disabled"
    assert "MOSDAC_ALLOW_L1B=false" in (by_id["mosdac_l1b"].get("detail") or "")


@pytest.mark.asyncio
async def test_mosdac_timeout_fails_hem_only():
    import asyncio

    jpeg = AsyncMock(return_value={"body": b"jpeg-bytes", "url": "http://imd", "status": "ok", "image_time": None})
    mosdac = AsyncMock(side_effect=asyncio.TimeoutError())
    imerg = AsyncMock(return_value={"ok": True})
    pack = {"ok": True, "counts": {}, "sensors": {"gibs_ir": True}, "incidents": []}
    settings, prev = _l1b_off()
    try:
        with (
            patch("app.providers.imd_insat.fetch_frame", jpeg),
            patch("app.providers.mosdac.ingest_latest", mosdac),
            patch("app.providers.gpm_imerg.fetch_pin", imerg),
            patch("app.science.storm_map.build", AsyncMock(return_value=pack)),
            patch("app.science.sat_lightning.refresh", AsyncMock(return_value={"ok": True, "cells": []})),
        ):
            await run_cycle()
    finally:
        settings.mosdac_allow_l1b = prev
    from app.store.ingest_status import snapshot

    by_id = {s["id"]: s for s in snapshot()["satellites"]}
    assert by_id["mosdac_hem"]["status"] == "fail"
    assert by_id["mosdac_hem"]["detail"] == "timeout"
    assert by_id["mosdac_l1b"]["status"] == "disabled"
    assert "MOSDAC_ALLOW_L1B=false" in (by_id["mosdac_l1b"].get("detail") or "")

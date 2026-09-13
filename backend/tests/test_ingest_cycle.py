from unittest.mock import AsyncMock, patch

import pytest

from app.ingest.cycle import run_cycle


@pytest.mark.asyncio
async def test_cycle_always_fetches_insat_jpeg():
    jpeg = AsyncMock(return_value=(b"jpeg-bytes", "http://imd", "ok"))
    mosdac = AsyncMock(return_value=[{"ok": True, "product": "3SIMG_L2B_HEM", "cached": True}])
    imerg = AsyncMock(return_value={"ok": True})
    pack = {
        "ok": True,
        "counts": {"predicted": 1},
        "sensors": {"gibs_ir": True},
        "need_second_frame": True,
        "incidents": [],
    }
    with (
        patch("app.providers.imd_insat.fetch_jpeg", jpeg),
        patch("app.providers.mosdac.ingest_latest", mosdac),
        patch("app.providers.gpm_imerg.fetch_pin", imerg),
        patch("app.science.storm_map.build", AsyncMock(return_value=pack)),
    ):
        out = await run_cycle()
    jpeg.assert_awaited()
    assert out["ok"] is True
    from app.store.ingest_status import snapshot

    snap = snapshot()
    assert snap["ready"] is True

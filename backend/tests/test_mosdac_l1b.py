from unittest.mock import AsyncMock, patch

import pytest

from app.providers.mosdac import L1B, MOSDAC_MAX_BYTES, ingest_latest


@pytest.mark.asyncio
async def test_ingest_latest_skips_l1b_when_not_allowed():
    searched = []

    async def fake_search(product, count=1):
        searched.append(product)
        return {"ok": True, "granules": [{"id": "g1", "identifier": "f.h5", "date": "2026-11-11"}]}

    async def fake_download(*args, **kwargs):
        raise AssertionError("L1B must not be downloaded when allow_l1b is false")

    with (
        patch("app.providers.mosdac.search", fake_search),
        patch("app.store.sat_frames.has_granule", return_value=True),
        patch("app.providers.mosdac.download_granule", fake_download),
        patch("app.providers.mosdac.logout", AsyncMock()),
        patch("app.providers.mosdac._quota_inc", return_value=True),
    ):
        rows = await ingest_latest(allow_l1b=False)
    assert searched == ["3SIMG_L2B_HEM"]
    assert not any(r.get("product") in L1B for r in rows)


@pytest.mark.asyncio
async def test_read_body_aborts_oversize_content_length(monkeypatch):
    import httpx
    from app.providers import http as httpp

    def handler(request):
        return httpx.Response(200, content=b"x" * 64, headers={"Content-Length": "391335177"})

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    monkeypatch.setattr(httpp, "client", lambda: client)
    try:
        with pytest.raises(OSError, match="content-length"):
            await httpp.read_body("http://example.test/l1b", max_bytes=MOSDAC_MAX_BYTES)
    finally:
        await client.aclose()

"""Single-flight and stale-while-revalidate."""

from __future__ import annotations

import asyncio

import pytest

from app import cache


@pytest.fixture(autouse=True)
def _reset():
    cache.clear()
    yield
    cache.clear()


@pytest.mark.asyncio
async def test_aget_single_flight():
    n = {"c": 0}

    async def factory():
        n["c"] += 1
        await asyncio.sleep(0.05)
        return {"n": n["c"]}

    a, b = await asyncio.gather(
        cache.aget("k", factory, ttl_s=10, swr_s=20),
        cache.aget("k", factory, ttl_s=10, swr_s=20),
    )
    assert n["c"] == 1
    assert a == b == {"n": 1}


@pytest.mark.asyncio
async def test_aget_serves_stale_while_refreshing():
    n = {"c": 0}

    async def factory():
        n["c"] += 1
        return n["c"]

    first = await cache.aget("swr", factory, ttl_s=0.05, swr_s=2.0)
    assert first == 1
    await asyncio.sleep(0.08)
    second = await cache.aget("swr", factory, ttl_s=0.05, swr_s=2.0)
    assert second == 1
    await asyncio.sleep(0.05)
    assert n["c"] >= 1

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


def test_byte_cap_evicts_lru(monkeypatch):
    import numpy as np

    monkeypatch.setenv("CLOUD_LIGHT", "1")
    cache.clear()
    monkeypatch.setattr(cache, "_MAX_BYTES_CLOUD", 8 * 1024 * 1024)
    monkeypatch.setattr(cache, "_MAX_CLOUD", 50)
    a = np.zeros((1024, 1024), dtype=np.float32)  # 4 MiB
    b = np.zeros((1024, 1024), dtype=np.float32)
    c = np.zeros((1024, 1024), dtype=np.float32)
    cache.set("a", a, 60)
    cache.set("b", b, 60)
    cache.set("c", c, 60)
    st = cache.stats()
    assert st["bytes"] <= 8 * 1024 * 1024
    assert st["entries"] <= 2
    assert cache.get("a") is None  # LRU evicted
    assert cache.get("c") is not None

"""In-memory TTL cache with single-flight and stale-while-revalidate.

Concurrent waiters for one key share a single factory call. After TTL a last-good
value is still served while one background refresh runs.
"""

from __future__ import annotations

import asyncio
import time
from collections import OrderedDict
from collections.abc import Awaitable, Callable
from threading import Lock
from typing import Any

_MAX = 512
_lock = Lock()
# key -> (fresh_until, swr_until, value)
_store: OrderedDict[str, tuple[float, float, Any]] = OrderedDict()
_inflight: dict[str, asyncio.Task[Any]] = {}
_alo: asyncio.Lock | None = None
_alo_loop: asyncio.AbstractEventLoop | None = None


def _unpack(hit: tuple) -> tuple[float, float, Any]:
    if len(hit) == 2:
        exp, val = hit
        return float(exp), float(exp), val
    fresh, swr, val = hit
    return float(fresh), float(swr), val


def _aloop() -> asyncio.Lock:
    global _alo, _alo_loop
    loop = asyncio.get_running_loop()
    if _alo is None or _alo_loop is not loop:
        _alo = asyncio.Lock()
        _alo_loop = loop
    return _alo


def get(key: str) -> Any | None:
    now = time.time()
    with _lock:
        hit = _store.get(key)
        if not hit:
            return None
        fresh, swr, value = _unpack(hit)
        if now < fresh:
            _store.move_to_end(key)
            return value
        if now >= swr:
            _store.pop(key, None)
        return None


def peek(key: str) -> Any | None:
    """Fresh or stale-within-SWR value. Does not start a refresh."""
    now = time.time()
    with _lock:
        hit = _store.get(key)
        if not hit:
            return None
        fresh, swr, value = _unpack(hit)
        if now < swr:
            _store.move_to_end(key)
            return value
        _store.pop(key, None)
        return None


def set(key: str, value: Any, ttl_s: float, swr_s: float = 0) -> None:
    now = time.time()
    ttl = max(0.0, float(ttl_s))
    extra = max(0.0, float(swr_s))
    with _lock:
        _store[key] = (now + ttl, now + ttl + extra, value)
        _store.move_to_end(key)
        while len(_store) > _MAX:
            _store.popitem(last=False)


def keys_prefix(prefix: str) -> list[str]:
    with _lock:
        return [k for k in _store if str(k).startswith(prefix)]


def clear() -> None:
    global _alo, _alo_loop
    with _lock:
        _store.clear()
    _inflight.clear()
    _alo = None
    _alo_loop = None


def remember(key: str, ttl_s: float, factory):
    hit = get(key)
    if hit is not None:
        return hit
    value = factory()
    set(key, value, ttl_s)
    return value


async def aget(
    key: str,
    factory: Callable[[], Awaitable[Any]],
    ttl_s: float,
    swr_s: float = 0,
) -> Any:
    """Return a cached value, coalescing concurrent misses and serving SWR stale."""
    now = time.time()
    stale: Any = None
    with _lock:
        hit = _store.get(key)
        if hit:
            fresh, swr, value = _unpack(hit)
            _store.move_to_end(key)
            if now < fresh:
                return value
            if now < swr:
                stale = value

    lock = _aloop()
    async with lock:
        with _lock:
            hit = _store.get(key)
            if hit:
                fresh, swr, value = _unpack(hit)
                if time.time() < fresh:
                    return value
                if time.time() < swr:
                    stale = value
        existing = _inflight.get(key)
        if stale is not None:
            if existing is None:
                task = asyncio.create_task(_refresh(key, factory, ttl_s, swr_s))
                _inflight[key] = task
            return stale
        if existing is not None:
            waiter = existing
        else:
            waiter = asyncio.create_task(_refresh(key, factory, ttl_s, swr_s))
            _inflight[key] = waiter

    try:
        return await waiter
    except Exception:
        if stale is not None:
            return stale
        raise


async def _refresh(
    key: str,
    factory: Callable[[], Awaitable[Any]],
    ttl_s: float,
    swr_s: float,
) -> Any:
    try:
        value = await factory()
        set(key, value, ttl_s, swr_s)
        return value
    finally:
        cur = asyncio.current_task()
        lock = _aloop()
        async with lock:
            if _inflight.get(key) is cur:
                _inflight.pop(key, None)

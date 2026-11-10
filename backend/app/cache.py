"""In-memory TTL cache with single-flight and stale-while-revalidate.

Concurrent waiters for one key share a single factory call. After TTL a last-good
value is still served while one background refresh runs. A byte cap evicts LRU
entries so decoded IR arrays cannot grow unbounded on a 512 MiB instance.
"""

from __future__ import annotations

import asyncio
import time
from collections import OrderedDict
from collections.abc import Awaitable, Callable
from threading import Lock
from typing import Any

_MAX = 512
_MAX_CLOUD = 128
_MAX_BYTES = 96 * 1024 * 1024
_MAX_BYTES_CLOUD = 48 * 1024 * 1024
_lock = Lock()
_bytes = 0
# key -> (fresh_until, swr_until, value, nbytes)
_store: OrderedDict[str, tuple[float, float, Any, int]] = OrderedDict()
_inflight: dict[str, asyncio.Task[Any]] = {}
_alo: asyncio.Lock | None = None
_alo_loop: asyncio.AbstractEventLoop | None = None


def _unpack(hit: tuple) -> tuple[float, float, Any]:
    if len(hit) == 2:
        exp, val = hit
        return float(exp), float(exp), val
    fresh, swr, val = hit[0], hit[1], hit[2]
    return float(fresh), float(swr), val


def _value_nbytes(value: Any) -> int:
    """Best-effort payload size so the LRU can evict by bytes, not just key count."""
    if value is None:
        return 0
    if isinstance(value, (bytes, bytearray, memoryview)):
        return int(len(value))
    if isinstance(value, str):
        return int(len(value) * 2)
    if isinstance(value, (int, float, bool)):
        return 24
    nbytes = getattr(value, "nbytes", None)
    if isinstance(nbytes, (int, float)):
        return int(nbytes)
    if isinstance(value, dict):
        return sum(_value_nbytes(k) + _value_nbytes(v) for k, v in value.items())
    # `set` is also this module's cache setter; always use the builtin type.
    import builtins

    if isinstance(value, (list, tuple, builtins.set)):
        return sum(_value_nbytes(x) for x in value)
    dump = getattr(value, "model_dump", None)
    if callable(dump):
        try:
            return _value_nbytes(dump())
        except Exception:
            return 4096
    return 64


def _limits() -> tuple[int, int]:
    try:
        from app.config import cloud_light

        if cloud_light():
            return _MAX_CLOUD, _MAX_BYTES_CLOUD
    except Exception:
        pass
    return _MAX, _MAX_BYTES


def _evict_unlocked() -> None:
    """Drop LRU entries until we are within the entry and byte caps."""
    global _bytes
    max_n, max_b = _limits()
    while _store and (len(_store) > max_n or _bytes > max_b):
        _k, ev = _store.popitem(last=False)
        nb = ev[3] if len(ev) >= 4 else 0
        _bytes = max(0, _bytes - int(nb))


def _drop_unlocked(key: str) -> None:
    global _bytes
    ev = _store.pop(key, None)
    if ev is not None and len(ev) >= 4:
        _bytes = max(0, _bytes - int(ev[3]))


def _aloop() -> asyncio.Lock:
    global _alo, _alo_loop
    loop = asyncio.get_running_loop()
    if _alo is None or _alo_loop is not loop:
        _alo = asyncio.Lock()
        _alo_loop = loop
    return _alo


def get(key: str) -> Any | None:
    global _bytes
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
            _drop_unlocked(key)
        return None


def peek(key: str) -> Any | None:
    """Fresh or stale-within-SWR value. Does not start a refresh."""
    global _bytes
    now = time.time()
    with _lock:
        hit = _store.get(key)
        if not hit:
            return None
        fresh, swr, value = _unpack(hit)
        if now < swr:
            _store.move_to_end(key)
            return value
        _drop_unlocked(key)
        return None


def set(key: str, value: Any, ttl_s: float, swr_s: float = 0) -> None:
    global _bytes
    now = time.time()
    ttl = max(0.0, float(ttl_s))
    extra = max(0.0, float(swr_s))
    nb = max(0, _value_nbytes(value))
    with _lock:
        old = _store.pop(key, None)
        if old is not None and len(old) >= 4:
            _bytes = max(0, _bytes - int(old[3]))
        _store[key] = (now + ttl, now + ttl + extra, value, nb)
        _store.move_to_end(key)
        _bytes += nb
        _evict_unlocked()


def keys_prefix(prefix: str) -> list[str]:
    with _lock:
        return [k for k in _store if str(k).startswith(prefix)]


def stats() -> dict[str, int]:
    with _lock:
        return {"entries": len(_store), "bytes": int(_bytes)}


def clear() -> None:
    global _alo, _alo_loop, _bytes
    with _lock:
        _store.clear()
        _bytes = 0
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

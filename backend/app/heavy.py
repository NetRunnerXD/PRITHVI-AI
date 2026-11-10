"""Single-flight slot for memory-heavy work on small cloud instances."""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from typing import AsyncIterator

_sem: asyncio.Semaphore | None = None
_loop: asyncio.AbstractEventLoop | None = None


def _slot() -> asyncio.Semaphore:
    global _sem, _loop
    loop = asyncio.get_running_loop()
    if _sem is None or _loop is not loop:
        from app.config import cloud_light

        _sem = asyncio.Semaphore(1 if cloud_light() else 2)
        _loop = loop
    return _sem


@asynccontextmanager
async def slot() -> AsyncIterator[None]:
    """On CLOUD_LIGHT / Render only one heavy build (storm-map, lightning) runs at a time."""
    async with _slot():
        yield

"""Pool of outbound Open-Meteo fetch workers (laptops / open dashboard tabs).

The API never dials into NAT. Devices connect a WebSocket and run GETs
against allowlisted Open-Meteo hosts from their own IP (separate quota).
"""

from __future__ import annotations

import asyncio
import time
import uuid
from typing import Any

from fastapi import WebSocket


class OmWorkerOffline(RuntimeError):
    pass


class OmHub:
    def __init__(self) -> None:
        self._sockets: list[WebSocket] = []
        self._rr = 0
        self._lock = asyncio.Lock()
        self._jobs: dict[str, asyncio.Future] = {}
        self.last_seen: float | None = None

    def online(self) -> bool:
        return bool(self._sockets)

    def n_online(self) -> int:
        return len(self._sockets)

    def status(self) -> dict[str, Any]:
        return {
            "online": self.online(),
            "n": self.n_online(),
            "last_seen": self.last_seen,
            "jobs": len(self._jobs),
        }

    def beat(self) -> None:
        self.last_seen = time.time()

    async def attach(self, ws: WebSocket) -> None:
        async with self._lock:
            if ws not in self._sockets:
                self._sockets.append(ws)
            self.beat()

    async def detach(self, ws: WebSocket) -> None:
        async with self._lock:
            self._sockets = [s for s in self._sockets if s is not ws]
        if not self._sockets:
            pending = list(self._jobs.items())
            self._jobs.clear()
            for _jid, fut in pending:
                if not fut.done():
                    fut.set_exception(OmWorkerOffline("all om workers disconnected"))

    def reset(self) -> None:
        self._sockets = []
        pending = list(self._jobs.items())
        self._jobs.clear()
        self.last_seen = None
        for _jid, fut in pending:
            if not fut.done():
                fut.set_exception(OmWorkerOffline("reset"))

    def complete(self, job_id: str, payload: dict[str, Any] | None = None, error: str | None = None) -> None:
        fut = self._jobs.pop(job_id, None)
        if fut is None or fut.done():
            return
        if error:
            fut.set_exception(RuntimeError(error))
            return
        fut.set_result(payload or {})

    def _pick(self) -> WebSocket | None:
        if not self._sockets:
            return None
        self._rr = (self._rr + 1) % len(self._sockets)
        return self._sockets[self._rr]

    async def submit(self, payload: dict[str, Any], timeout: float = 20.0) -> dict[str, Any]:
        ws = self._pick()
        if ws is None:
            raise OmWorkerOffline("no om workers")
        job_id = uuid.uuid4().hex
        loop = asyncio.get_running_loop()
        fut: asyncio.Future = loop.create_future()
        self._jobs[job_id] = fut
        body = {"type": "fetch", "id": job_id, **payload}
        try:
            await ws.send_json(body)
        except Exception as exc:
            self._jobs.pop(job_id, None)
            async with self._lock:
                self._sockets = [s for s in self._sockets if s is not ws]
            raise OmWorkerOffline(f"om worker send failed: {exc}") from exc
        try:
            return await asyncio.wait_for(fut, timeout)
        except TimeoutError as exc:
            self._jobs.pop(job_id, None)
            raise OmWorkerOffline("om worker timed out") from exc


hub = OmHub()

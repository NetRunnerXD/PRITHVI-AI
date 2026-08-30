"""In-process registry for a home Ollama worker.

The PC connects out (WebSocket). The API never dials into NAT.
"""

from __future__ import annotations

import asyncio
import time
import uuid
from typing import Any

from fastapi import WebSocket


class WorkerOffline(RuntimeError):
    pass


class WorkerHub:
    def __init__(self) -> None:
        self._ws: WebSocket | None = None
        self._lock = asyncio.Lock()
        self._jobs: dict[str, asyncio.Future] = {}
        self.last_seen: float | None = None

    def online(self) -> bool:
        return self._ws is not None

    def status(self) -> dict[str, Any]:
        return {
            "online": self.online(),
            "last_seen": self.last_seen,
            "jobs": len(self._jobs),
        }

    def beat(self) -> None:
        self.last_seen = time.time()

    async def attach(self, ws: WebSocket) -> None:
        async with self._lock:
            old = self._ws
            self._ws = ws
            self.beat()
        if old is not None and old is not ws:
            try:
                await old.close(code=1000)
            except Exception:
                pass
            self._fail_all("worker replaced")

    async def detach(self, ws: WebSocket) -> None:
        async with self._lock:
            if self._ws is ws:
                self._ws = None
        self._fail_all("worker disconnected")

    def reset(self) -> None:
        self._ws = None
        self._fail_all("reset")
        self.last_seen = None

    def _fail_all(self, reason: str) -> None:
        pending = list(self._jobs.items())
        self._jobs.clear()
        for _jid, fut in pending:
            if not fut.done():
                fut.set_exception(WorkerOffline(reason))

    def complete(self, job_id: str, payload: dict[str, Any] | None = None, error: str | None = None) -> None:
        fut = self._jobs.pop(job_id, None)
        if fut is None or fut.done():
            return
        if error:
            fut.set_exception(RuntimeError(error))
            return
        fut.set_result(payload or {})

    async def submit(self, payload: dict[str, Any], timeout: float = 120.0) -> dict[str, Any]:
        ws = self._ws
        if ws is None:
            raise WorkerOffline("home ollama offline")
        job_id = uuid.uuid4().hex
        loop = asyncio.get_running_loop()
        fut: asyncio.Future = loop.create_future()
        self._jobs[job_id] = fut
        body = {"type": "job", "id": job_id, **payload}
        try:
            await ws.send_json(body)
        except Exception as exc:
            self._jobs.pop(job_id, None)
            async with self._lock:
                if self._ws is ws:
                    self._ws = None
            raise WorkerOffline(f"worker send failed: {exc}") from exc
        try:
            return await asyncio.wait_for(fut, timeout)
        except TimeoutError as exc:
            self._jobs.pop(job_id, None)
            raise WorkerOffline("home ollama timed out") from exc


hub = WorkerHub()

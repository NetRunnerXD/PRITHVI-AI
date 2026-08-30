"""Home Ollama worker hub: auth, dispatch, timeout, chat routing."""

from __future__ import annotations

import asyncio

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from app.config import get_settings
from app.llm import ollama_client
from app.llm.worker_hub import WorkerOffline, hub


def setup_function():
    get_settings.cache_clear()
    hub.reset()


def teardown_function():
    hub.reset()
    get_settings.cache_clear()


class FakeWS:
    def __init__(self) -> None:
        self.sent: list[dict] = []
        self.closed = False

    async def send_json(self, body):
        self.sent.append(body)

    async def close(self, code=1000):
        self.closed = True


def test_home_status_unconfigured():
    from app.main import app

    with TestClient(app) as c:
        r = c.get("/api/llm/home")
        assert r.status_code == 200
        body = r.json()
        assert body["ok"] is True
        assert body["ws"] == "/api/llm/worker"
        assert "configured" in body


def test_ws_rejects_missing_token(monkeypatch):
    from app.config import Settings
    from app.main import app

    monkeypatch.setattr("app.api.llm_worker.get_settings", lambda: Settings(llm_worker_token=""))
    with TestClient(app) as c:
        with c.websocket_connect("/api/llm/worker") as ws:
            msg = ws.receive_json()
            assert msg["type"] == "error"
            assert "LLM_WORKER_TOKEN" in msg["error"]


def test_ws_rejects_wrong_token(monkeypatch):
    from app.config import Settings
    from app.main import app

    monkeypatch.setattr("app.api.llm_worker.get_settings", lambda: Settings(llm_worker_token="secret"))
    with TestClient(app) as c:
        with c.websocket_connect("/api/llm/worker?token=nope") as ws:
            msg = ws.receive_json()
            assert msg["type"] == "error"
            assert "mismatch" in msg["error"]


def test_ws_accepts_token(monkeypatch):
    from app.config import Settings
    from app.main import app

    monkeypatch.setattr("app.api.llm_worker.get_settings", lambda: Settings(llm_worker_token="secret"))
    with TestClient(app) as c:
        with c.websocket_connect("/api/llm/worker?token=secret") as ws:
            hello = ws.receive_json()
            assert hello["type"] == "hello"
            assert hub.online()


@pytest.mark.asyncio
async def test_hub_submit_roundtrip():
    ws = FakeWS()
    await hub.attach(ws)
    assert hub.online()

    async def reply():
        await asyncio.sleep(0.01)
        jid = ws.sent[0]["id"]
        hub.complete(jid, {"content": "from-home", "tool_calls": []})

    asyncio.create_task(reply())
    out = await hub.submit({"model": "qwen2.5:3b", "messages": []}, timeout=2)
    assert out["content"] == "from-home"
    assert ws.sent[0]["type"] == "job"


@pytest.mark.asyncio
async def test_hub_timeout():
    ws = FakeWS()
    await hub.attach(ws)
    with pytest.raises(WorkerOffline, match="timed out"):
        await hub.submit({"messages": []}, timeout=0.05)


@pytest.mark.asyncio
async def test_chat_uses_home_worker(monkeypatch):
    async def fake_submit(payload, timeout=120.0):
        return {"content": "home-ok", "tool_calls": []}

    monkeypatch.setattr(hub, "online", lambda: True)
    monkeypatch.setattr(hub, "submit", fake_submit)
    out = await ollama_client.chat([{"role": "user", "content": "hi"}])
    assert out["content"] == "home-ok"
    assert out["via"] == "home-worker"
    assert out["provider"] == "ollama"


@pytest.mark.asyncio
async def test_chat_offline_worker_uses_http(monkeypatch):
    monkeypatch.setattr(hub, "online", lambda: False)

    class Boom:
        async def create(self, **kwargs):
            raise RuntimeError("no local ollama")

    class FakeClient:
        chat = type("C", (), {"completions": Boom()})()

    monkeypatch.setattr(ollama_client, "client", lambda: FakeClient())
    out = await ollama_client.chat([{"role": "user", "content": "hi"}])
    assert out.get("error")
    assert "no local ollama" in str(out["error"])


@pytest.mark.asyncio
async def test_ping_home_online(monkeypatch):
    monkeypatch.setattr(hub, "online", lambda: True)
    ok, msg = await ollama_client.ping()
    assert ok
    assert "home-online" in msg

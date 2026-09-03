import base64

from fastapi.testclient import TestClient

from app.config import Settings
from app.main import app
from app.services import speech as voice

client = TestClient(app)


def test_speech_status_off_by_default():
    voice.reset_status_cache()
    r = client.get("/api/speech/status")
    assert r.status_code == 200
    body = r.json()
    assert body["stt"] is False
    assert body["tts"] is False
    assert body["fallback"] == "web-speech"
    assert body["stt_langs"] == []


def test_stt_unconfigured():
    r = client.post(
        "/api/speech/stt",
        files={"file": ("clip.wav", b"RIFF....", "audio/wav")},
        data={"language": "hi"},
    )
    assert r.status_code == 503
    assert r.json()["detail"]["fallback"] == "web-speech"


def test_tts_unconfigured():
    r = client.post("/api/speech/tts", json={"text": "नमस्ते", "language": "hi"})
    assert r.status_code == 503


def test_stt_lang_not_in_14(monkeypatch):
    async def boom(*_a, **_k):
        raise ValueError("stt_lang")

    monkeypatch.setattr(voice, "transcribe", boom)
    r = client.post(
        "/api/speech/stt",
        files={"file": ("clip.wav", b"xx", "audio/wav")},
        data={"language": "sat"},
    )
    assert r.status_code == 501
    assert r.json()["detail"]["fallback"] == "web-speech"


def test_plain_and_bcp():
    assert voice.bcp_for("hi") == "hi-IN"
    assert voice.bcp_for("ne") == "ne-IN"
    assert voice.plain_for_speech("**12 mm** rain") == "12 mm rain"
    assert voice.lang_id("ta-IN") == "ta"


def test_transcribe_poll(monkeypatch):
    class FakeResp:
        def __init__(self, code, body):
            self.status_code = code
            self._body = body
            self.headers = {"content-type": "application/json"}

        def json(self):
            return self._body

    class FakeClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return None

        async def post(self, url, **kwargs):
            assert "batch/transcribe" in url
            return FakeResp(201, {"job_id": "batch_1", "status": "queued"})

        async def get(self, url, **kwargs):
            if "status" in url:
                return FakeResp(200, {"status": "completed", "text": "आज बारिश होगी"})
            return FakeResp(202, {})

    monkeypatch.setattr(voice.httpx, "AsyncClient", lambda **k: FakeClient())
    monkeypatch.setattr(voice, "get_settings", lambda: Settings(vexyl_stt_url="http://stt.example:8091"))
    import asyncio

    out = asyncio.run(voice.transcribe(b"wav", "a.wav", "hi"))
    assert out["text"] == "आज बारिश होगी"
    assert out["lang"] == "hi"


def test_synthesize_b64(monkeypatch):
    wav = b"RIFFWAV"
    b64 = base64.b64encode(wav).decode()

    class FakeResp:
        def __init__(self, code, body):
            self.status_code = code
            self._body = body
            self.headers = {"content-type": "application/json"}

        def json(self):
            return self._body

    class FakeClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return None

        async def post(self, url, **kwargs):
            return FakeResp(201, {"job_id": "t1", "status": "queued"})

        async def get(self, url, **kwargs):
            return FakeResp(200, {"status": "completed", "audio_b64": b64})

    monkeypatch.setattr(voice.httpx, "AsyncClient", lambda **k: FakeClient())
    monkeypatch.setattr(voice, "get_settings", lambda: Settings(vexyl_tts_url="http://tts.example:8092"))
    import asyncio

    audio, mime = asyncio.run(voice.synthesize("नमस्ते", "hi"))
    assert audio == wav
    assert mime == "audio/wav"


def test_tts_cap():
    assert len(voice.plain_for_speech("x" * 2000)) >= 1
    long = "हिंदी " * 400
    assert len(long) > voice.TTS_MAX_CHARS

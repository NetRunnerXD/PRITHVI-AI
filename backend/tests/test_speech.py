import base64

from fastapi.testclient import TestClient

from app.config import Settings
from app.main import app
from app.services import speech as voice

client = TestClient(app)


def test_speech_status_off_by_default(monkeypatch):
    voice.reset_status_cache()

    async def down(_url):
        return False

    monkeypatch.setattr(voice, "_health", down)
    monkeypatch.setattr(
        "app.services.device_hw.voice_ready",
        lambda: {"stt": False, "tts": False, "detail": "", "langs": []},
    )
    r = client.get("/api/speech/status")
    assert r.status_code == 200
    body = r.json()
    assert body["stt"] is False
    assert body["tts"] is False
    assert body["fallback"] == "web-speech"
    assert body["stt_langs"] == []
    assert body["tts_langs"] == []
    assert body["engine"]["tts"] is None


def test_stt_unconfigured():
    r = client.post(
        "/api/speech/stt",
        files={"file": ("clip.wav", b"RIFF....", "audio/wav")},
        data={"language": "hi"},
    )
    assert r.status_code == 503
    assert r.json()["detail"]["fallback"] == "web-speech"


def test_tts_unconfigured(monkeypatch):
    async def down(*_a, **_k):
        raise RuntimeError("tts_failed")

    async def vexyl(*_a, **_k):
        raise AssertionError("vexyl")

    monkeypatch.setattr("app.services.device_hw.speak_local", down)
    monkeypatch.setattr(voice, "synthesize", vexyl)
    r = client.post("/api/speech/tts", json={"text": "नमस्ते", "language": "hi"})
    assert r.status_code == 503


def test_stt_langs_are_the_22_scheduled():
    assert len(voice.STT_LANGS) == 22
    assert "sat" in voice.STT_LANGS and "brx" in voice.STT_LANGS
    assert "en" not in voice.STT_LANGS


def test_stt_lang_not_scheduled(monkeypatch):
    async def boom(*_a, **_k):
        raise ValueError("stt_lang")

    monkeypatch.setattr(voice, "transcribe", boom)
    r = client.post(
        "/api/speech/stt",
        files={"file": ("clip.wav", b"xx", "audio/wav")},
        data={"language": "fr"},
    )
    assert r.status_code == 501
    assert r.json()["detail"]["fallback"] == "web-speech"


def test_stt_english_uses_whisper_not_indic(monkeypatch):
    async def boom(*_a, **_k):
        raise AssertionError("indic sidecar")

    monkeypatch.setattr(voice, "transcribe", boom)
    monkeypatch.setattr("app.services.device_hw.transcribe_english", lambda _data: "rain tomorrow")
    r = client.post(
        "/api/speech/stt",
        files={"file": ("clip.wav", b"RIFF", "audio/wav")},
        data={"language": "en"},
    )
    assert r.status_code == 200
    assert r.json() == {"text": "rain tomorrow", "lang": "en"}


def test_stt_auto_indic_uses_one_conformer_pass(monkeypatch):
    monkeypatch.setattr(
        "app.services.device_hw.transcribe_detect",
        lambda _data: {"text": "whisper", "lang": "hi"},
    )

    async def indic(_data, _filename, language):
        assert language == "hi"
        return {"text": "आज बारिश", "lang": "hi"}

    monkeypatch.setattr(voice, "transcribe", indic)
    r = client.post(
        "/api/speech/stt",
        files={"file": ("clip.wav", b"RIFF", "audio/wav")},
        data={"language": "auto"},
    )
    assert r.status_code == 200
    assert r.json()["text"] == "आज बारिश"
    assert r.json()["lang"] == "hi"


def test_stt_auto_keeps_whisper_when_sidecar_is_down(monkeypatch):
    monkeypatch.setattr(
        "app.services.device_hw.transcribe_detect",
        lambda _data: {"text": "kal barish", "lang": "hi"},
    )

    async def down(*_a, **_k):
        raise RuntimeError("stt_unconfigured")

    monkeypatch.setattr(voice, "transcribe", down)
    r = client.post(
        "/api/speech/stt",
        files={"file": ("clip.wav", b"RIFF", "audio/wav")},
        data={"language": "auto"},
    )
    assert r.status_code == 200
    assert r.json() == {"text": "kal barish", "lang": "hi"}


def test_tts_hindi_uses_local_speaker(monkeypatch):
    async def speak(text, language, timeout_s=180.0):
        assert language == "hi"
        assert "बारिश" in text
        assert timeout_s
        return b"RIFF....", "audio/wav"

    async def vexyl(*_a, **_k):
        raise AssertionError("vexyl")

    monkeypatch.setattr("app.services.device_hw.speak_local", speak)
    monkeypatch.setattr(voice, "synthesize", vexyl)
    r = client.post("/api/speech/tts", json={"text": "आज बारिश", "language": "hi"})
    assert r.status_code == 200
    assert r.content.startswith(b"RIFF")
    assert r.headers["content-type"].startswith("audio/")


def test_tts_dogri_is_not_sent_to_vexyl(monkeypatch):
    async def speak(*_a, **_k):
        raise AssertionError("fastspeech")

    async def vexyl(*_a, **_k):
        raise AssertionError("vexyl")

    monkeypatch.setattr("app.services.device_hw.speak_local", speak)
    monkeypatch.setattr(voice, "synthesize", vexyl)
    r = client.post("/api/speech/tts", json={"text": "डोगरी", "language": "doi"})
    assert r.status_code == 501
    assert r.json()["detail"]["error"] == "tts_lang"
    assert "doi" not in r.json()["detail"]["tts_langs"]


def test_status_voices_are_fastspeech_not_vexyl(monkeypatch):
    voice.reset_status_cache()

    async def up(_url):
        return True

    monkeypatch.setattr(voice, "_health", up)
    monkeypatch.setattr(
        "app.services.device_hw.voice_ready",
        lambda: {"stt": False, "tts": True, "detail": "", "langs": ["hi", "bn", "en"]},
    )
    r = client.get("/api/speech/status")
    body = r.json()
    assert body["tts_langs"] == ["bn", "hi", "en"]
    assert "doi" not in body["tts_langs"]
    assert body["engine"]["tts"] == "fastspeech2"
    assert len(body["stt_langs"]) == 22


def test_tts_english_uses_local_speaker(monkeypatch):
    async def speak(text, timeout_s=60.0):
        assert "Rain" in text
        assert timeout_s
        return b"RIFF....", "audio/wav"

    monkeypatch.setattr("app.services.device_hw.speak_english", speak)
    r = client.post("/api/speech/tts", json={"text": "Rain tomorrow", "language": "en"})
    assert r.status_code == 200
    assert r.content.startswith(b"RIFF")
    assert r.headers["content-type"].startswith("audio/")


def test_fs2_text_drops_degree_sign():
    from app.services.device_hw import fs2_text

    raw = "సుమారు 32 °C తేలికపాటి ఉష్ణోగ్రతను ఆస్వాదించండి."
    out = fs2_text(raw)
    assert "°" not in out
    assert "32" in out
    assert "ఆస్వాదించండి" in out


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

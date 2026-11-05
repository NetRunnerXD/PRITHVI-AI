import io
import wave

from fastapi.testclient import TestClient

from app.api import device as device_api
from app.main import app
from app.services import device_hw
from app.services.device_hw import oled_card, resample_pcm16, wav_mono16

client = TestClient(app)


class _Cur:
    temp_c = 31.5
    sky_kind = "rain"
    precip_1h_mm = 2.0
    aqi = 88
    om_us_aqi = 90
    is_day = True


class _Warn:
    hazard = "heat"
    title = "Heat alert"


class _Snap:
    class location:
        place_name = "Haldia"
        label = "Haldia, West Bengal"

    class descriptive:
        current = _Cur()

    class prescriptive:
        warnings = [_Warn()]
        actions = []


def _wav() -> bytes:
    return wav_mono16(b"\x01\x00" * 160, 16000)


def test_oled_card_uses_snapshot_numbers():
    card = oled_card(_Snap())
    assert card["place"] == "Haldia"
    assert card["temp_c"] == 31.5
    assert card["sky_kind"] == "rain"
    assert card["hazard"] == "heat"
    assert card["aqi"] == 88


def test_resample_halves_a_32k_tone():
    pcm = b"\x00\x10" * 32
    out = resample_pcm16(pcm, 32000, 16000)
    assert len(out) == 32 or len(out) == 34


def test_face_returns_oled_card(monkeypatch):
    async def fake_core(loc, locale="en", **_k):
        assert locale == "en"
        return _Snap(), True

    monkeypatch.setattr(device_api, "build_core", fake_core)
    response = client.get("/api/device/face?place=Haldia")
    assert response.status_code == 200
    body = response.json()
    assert body["place"] == "Haldia"
    assert body["temp_c"] == 31.5
    assert "series" not in body


def test_turn_rejects_a_short_body():
    response = client.post("/api/device/turn", content=b"nope", headers={"content-type": "audio/wav"})
    assert response.status_code == 400
    assert response.json()["error"] == "empty_audio"


def test_turn_english_wav(monkeypatch):
    seen = {}

    def fake_stt(data: bytes) -> str:
        seen["wav"] = data[:4]
        return "Will it rain today"

    async def fake_agent(payload):
        seen["locale"] = payload.output_locale
        seen["message"] = payload.message
        yield {"type": "final", "message": {"content": "Light rain, about 2 mm."}}

    async def fake_tts(text):
        seen["tts_lang"] = "en"
        seen["spoken"] = text
        return _wav(), "audio/wav"

    async def fake_core(loc, locale="en", **_k):
        return _Snap(), True

    monkeypatch.setattr(device_api, "transcribe_english", fake_stt)
    monkeypatch.setattr(device_api, "run_agent", fake_agent)
    monkeypatch.setattr(device_api, "speak_english", fake_tts)
    monkeypatch.setattr(device_api, "build_core", fake_core)

    response = client.post(
        "/api/device/turn?place=Haldia",
        content=_wav(),
        headers={"content-type": "audio/wav", "x-prithvi-locale": "hi"},
    )
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("audio/wav")
    assert response.headers["x-prithvi-lang"] == "en"
    assert response.headers["x-prithvi-place"] == "Haldia"
    assert seen["locale"] == "en"
    assert seen["tts_lang"] == "en"
    assert seen["message"] == "Will it rain today"
    with wave.open(io.BytesIO(response.content), "rb") as wf:
        assert wf.getframerate() == 16000
        assert wf.getnchannels() == 1


def test_turn_stt_missing(monkeypatch):
    def missing(_data: bytes) -> str:
        raise RuntimeError("stt_unconfigured")

    monkeypatch.setattr(device_api, "transcribe_english", missing)
    response = client.post("/api/device/turn", content=_wav(), headers={"content-type": "audio/wav"})
    assert response.status_code == 503
    assert response.json()["error"] == "stt_unconfigured"


def test_transcribe_forces_english(monkeypatch):
    class Seg:
        text = "hello rain"

    class Model:
        def transcribe(self, path, language="en", vad_filter=True):
            assert language == "en"
            assert vad_filter is True
            return [Seg()], None

    monkeypatch.setattr(device_hw, "_english_model", lambda: Model())
    assert device_hw.transcribe_english(_wav()) == "hello rain"

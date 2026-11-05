import os

import pytest

from app import cache
from app.i18n.detect import SCHEDULED_22, detect_lang, has_script, pick_output_locale, script_of
from app.i18n.mt import MTResult, _sidecar_pair, inbound, outbound, protect, restore, translate


@pytest.fixture(autouse=True)
def _clear_mt_cache():
    cache.clear()
    yield
    cache.clear()


def test_parse_gtx_shapes():
    from app.i18n.mt import _parse_gtx

    nested = [[["হাওড়া এখন ২৯", "Howrah now", None, None]], None, "en"]
    body, det = _parse_gtx(nested)
    assert "হাওড়া" in body
    assert det == "en"

    chrome = ["हावड़ा: 29.4°C, 7.1 मिमी।"]
    body, det = _parse_gtx(chrome)
    assert body.startswith("हावड़ा")
    assert det is None

    dj = {"sentences": [{"trans": "বৃষ্টি "}, {"trans": "হচ্ছে।"}], "src": "en"}
    body, det = _parse_gtx(dj)
    assert body == "বৃষ্টি হচ্ছে।"
    assert det == "en"


def test_protect_restore_numbers_and_acronyms():
    src = "CPCB AQI 47.2 and 800-1200 liters. IMD CAP. Open-Meteo."
    masked, held = protect(src)
    assert "47.2" not in masked
    assert "800" not in masked
    assert "CPCB" not in masked
    assert "AQI" not in masked
    assert "IMD" not in masked
    assert "Open-Meteo" not in masked
    assert "XLT" not in masked
    assert "⟦" in masked
    assert restore(masked, held) == src


def test_protect_keeps_iso_date_as_one_token():
    src = "Haldia 2026-08-28: 4.2 mm, 32°C, CPCB AQI 47."
    masked, held = protect(src)
    assert "2026-08-28" in held
    assert "2026-08-28" not in masked
    assert restore(masked, held) == src


def test_protect_is_case_insensitive_for_sources():
    masked, held = protect("open-meteo and cpcb aqi 12")
    assert "open-meteo" not in masked.lower()
    assert "cpcb" not in masked.lower()
    assert restore(masked, held) == "open-meteo and cpcb aqi 12"


def test_detect_scripts_and_english():
    assert detect_lang("পশ্চিমবঙ্গের কোন জেলায় বন্যা?") == "bn"
    assert detect_lang("पश्चिम बंगाल के कौन से जिले") == "hi"
    assert script_of("அடுத்த மூன்று நாட்களில் மழை?") == "ta"
    assert detect_lang("Should I irrigate now in Nadia?") == "en"
    assert has_script("এখন সেচ দেবেন না।", "bn")
    assert has_script("आज सिंचाई न करें।", "hi")
    assert not has_script("Hold irrigation today.", "bn")


def test_pick_output_locale():
    # Reply-in Auto follows the question
    assert pick_output_locale(output_locale="auto", locale_hint="en", detected="bn") == "bn"
    assert pick_output_locale(output_locale="auto", locale_hint="en", detected="hi") == "hi"
    assert pick_output_locale(output_locale="auto", locale_hint="en", detected="ta") == "ta"
    assert pick_output_locale(output_locale="auto", locale_hint="hi", detected="en") == "en"
    # Explicit EN / HI / BN always wins over the typed language
    assert pick_output_locale(output_locale="en", locale_hint="en", detected="bn") == "en"
    assert pick_output_locale(output_locale="en", locale_hint="bn", detected="bn") == "en"
    assert pick_output_locale(output_locale="hi", locale_hint="en", detected="bn") == "hi"
    assert pick_output_locale(output_locale="bn", locale_hint="bn", detected="en") == "bn"
    # Missing Reply-in falls back to UI hint
    assert pick_output_locale(output_locale=None, locale_hint="hi", detected="en") == "hi"


@pytest.mark.asyncio
async def test_inbound_english_is_identity():
    pack = await inbound("Should I irrigate now in Nadia?", "en")
    assert pack.ok
    assert pack.engine == "identity"
    assert pack.tgt == "en"
    assert "irrigate" in pack.text.lower()


@pytest.mark.asyncio
async def test_outbound_english_is_identity():
    pack = await outbound("Rain 54.2 mm next 3 days.", "en")
    assert pack.engine == "identity"
    assert pack.text.startswith("Rain")


@pytest.mark.asyncio
async def test_translate_restores_locked_tokens(monkeypatch):
    async def fake_gtx(text, src, tgt):
        return MTResult(
            text=text.replace("rain", "বৃষ্টি"),
            src="en",
            tgt="bn",
            engine="google-gtx",
            ok=True,
        )

    async def no_memory(*_a, **_k):
        raise AssertionError("MyMemory should not run when Google succeeds")

    monkeypatch.setattr("app.i18n.mt._gtx", fake_gtx)
    monkeypatch.setattr("app.i18n.mt._mymemory", no_memory)
    out = await translate("next 3 days 54.2 mm rain. CPCB AQI 47.", "en", "bn")
    assert out.ok
    assert out.engine == "google-gtx"
    assert "54.2" in out.text
    assert "47" in out.text
    assert "CPCB" in out.text
    assert "AQI" in out.text
    assert "বৃষ্টি" in out.text


@pytest.mark.asyncio
async def test_translate_fails_when_engine_drops_lock(monkeypatch):
    from app.i18n.mt import held_missing

    async def drop_token(text, src, tgt):
        return MTResult(text=text.replace("⟦1⟧", ""), src="en", tgt="bn", engine="google-gtx", ok=True)

    monkeypatch.setattr("app.i18n.mt._gtx", drop_token)
    monkeypatch.setattr("app.i18n.mt._mymemory", drop_token)
    out = await translate("Haldia 2026-08-28: 4.2 mm rain.", "en", "bn")
    assert not out.ok


@pytest.mark.asyncio
async def test_translate_fails_on_leaked_brackets(monkeypatch):
    async def leak(text, src, tgt):
        return MTResult(text=text + " ⟦4", src="en", tgt="hi", engine="mymemory", ok=True)

    monkeypatch.setattr("app.i18n.mt._gtx", leak)
    monkeypatch.setattr("app.i18n.mt._mymemory", leak)
    out = await translate("Howrah is 29.4 C.", "en", "hi")
    assert not out.ok


@pytest.mark.asyncio
async def test_inbound_translates_from_detected_language(monkeypatch):
    seen: list[tuple[str, str]] = []

    async def fake_gtx(text, src, tgt):
        seen.append((src, tgt))
        return MTResult(text="Which West Bengal districts will flood?", src="bn", tgt="en", engine="google-gtx", ok=True)

    monkeypatch.setattr("app.i18n.mt._gtx", fake_gtx)
    pack = await inbound("পশ্চিমবঙ্গের কোন কোন জেলায় বন্যার সম্ভাবনা বেশি?", "en")
    assert pack.ok
    assert pack.src == "bn"
    assert seen[0] == ("bn", "en")
    assert "flood" in pack.text.lower()


@pytest.mark.asyncio
async def test_outbound_sends_whole_document(monkeypatch):
    calls: list[str] = []

    async def fake_gtx(text, src, tgt):
        calls.append(text)
        return MTResult(text=text.replace("Rain", "বৃষ্টি"), src="en", tgt="bn", engine="google-gtx", ok=True)

    async def no_memory(*_a, **_k):
        raise AssertionError("should not chunk to MyMemory when whole gtx works")

    monkeypatch.setattr("app.i18n.mt._gtx", fake_gtx)
    monkeypatch.setattr("app.i18n.mt._mymemory", no_memory)
    draft = "Rain 12.4 mm next 3 days. CPCB AQI 47.\n" * 40
    out = await outbound(draft, "bn")
    assert out.ok
    assert len(calls) == 1
    assert "12.4" in out.text
    assert "47" in out.text
    assert "বৃষ্টি" in out.text


@pytest.mark.asyncio
async def test_inbound_uses_mt_for_indic(monkeypatch):
    async def fake_gtx(text, src, tgt):
        return MTResult(
            text="Which districts in West Bengal will flood? List them.",
            src="bn",
            tgt="en",
            engine="google-gtx",
            ok=True,
        )

    monkeypatch.setattr("app.i18n.mt._gtx", fake_gtx)
    pack = await inbound("পশ্চিমবঙ্গের কোন কোন জেলায় বন্যার সম্ভাবনা বেশি? তালিকা দিন।", "en")
    assert pack.ok
    assert pack.src == "bn"
    assert pack.tgt == "en"
    assert "West Bengal" in pack.text
    assert "flood" in pack.text.lower()


def test_sidecar_flores_covers_the_22():
    for code in SCHEDULED_22:
        to_indic = _sidecar_pair("en", code)
        to_en = _sidecar_pair(code, "en")
        assert to_indic is not None and to_indic[0] == "eng_Latn" and to_indic[1]
        assert to_en is not None and to_en[1] == "eng_Latn" and to_en[0]
    assert _sidecar_pair("en", "mni") == ("eng_Latn", "mni_Mtei")
    assert _sidecar_pair("kok", "en") == ("gom_Deva", "eng_Latn")
    assert _sidecar_pair("ks", "en") == ("kas_Arab", "eng_Latn")
    assert _sidecar_pair("en", "sat") == ("eng_Latn", "sat_Olck")
    assert _sidecar_pair("en", "or") == ("eng_Latn", "ory_Orya")
    assert _sidecar_pair("en", "brx") == ("eng_Latn", "brx_Deva")
    assert _sidecar_pair("fr", "en") is None
    assert _sidecar_pair("hi", "bn") is None


class _Cfg:
    def __init__(self, url: str):
        self.mt_sidecar_url = url
        self.translate_enabled = True


class _Resp:
    def __init__(self, body: str, status: int = 200):
        self.status_code = status
        self._body = body

    def json(self):
        return {"text": self._body}


def _patch_sidecar(monkeypatch, post, *, url: str = "http://127.0.0.1:8093"):
    made = {"n": 0}

    class _Client:
        def __init__(self, *args, **kwargs):
            made["n"] += 1

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def post(self, path, json=None, **kwargs):
            return await post(path, json)

    monkeypatch.setattr("app.i18n.mt.get_settings", lambda: _Cfg(url))
    monkeypatch.setattr("app.i18n.mt.httpx.AsyncClient", _Client)
    return made


@pytest.mark.asyncio
async def test_sidecar_restores_locks_and_skips_gtx(monkeypatch):
    posts: list[dict] = []

    async def post(path, payload):
        posts.append(payload)
        assert path.endswith("/translate")
        assert "⟦" not in payload["text"]
        assert "54.2" not in payload["text"]
        assert "CPCB" not in payload["text"]
        return _Resp("বৃষ্টি " + payload["text"])

    async def boom(*_a, **_k):
        raise AssertionError("Google should not run when the sidecar succeeds")

    _patch_sidecar(monkeypatch, post)
    monkeypatch.setattr("app.i18n.mt._gtx", boom)
    monkeypatch.setattr("app.i18n.mt._mymemory", boom)
    out = await translate("next 3 days 54.2 mm rain. CPCB AQI 47.", "en", "bn")
    assert out.ok
    assert out.engine == "indictrans2"
    assert len(posts) == 2
    assert {p["src"] for p in posts} == {"eng_Latn"}
    assert {p["tgt"] for p in posts} == {"ben_Beng"}
    assert "54.2" in out.text
    assert "47" in out.text
    assert "CPCB" in out.text
    assert "AQI" in out.text
    assert "বৃষ্টি" in out.text


@pytest.mark.asyncio
async def test_sidecar_down_falls_through_to_gtx(monkeypatch):
    import httpx

    async def post(path, payload):
        raise httpx.ConnectError("down")

    seen: list[str] = []

    async def fake_gtx(text, src, tgt):
        seen.append(tgt)
        return MTResult(text="বৃষ্টি " + text, src=src, tgt=tgt, engine="google-gtx", ok=True)

    async def no_memory(*_a, **_k):
        raise AssertionError("MyMemory")

    _patch_sidecar(monkeypatch, post)
    monkeypatch.setattr("app.i18n.mt._gtx", fake_gtx)
    monkeypatch.setattr("app.i18n.mt._mymemory", no_memory)
    out = await translate("next 3 days 54.2 mm rain.", "en", "bn")
    assert out.ok
    assert out.engine == "google-gtx"
    assert seen == ["bn"]
    assert "54.2" in out.text
    assert "বৃষ্টি" in out.text


@pytest.mark.asyncio
async def test_sidecar_bodo_is_direct(monkeypatch):
    async def post(path, payload):
        assert payload["tgt"] == "brx_Deva"
        return _Resp("बारिश " + payload["text"])

    async def boom(*_a, **_k):
        raise AssertionError("Google")

    _patch_sidecar(monkeypatch, post)
    monkeypatch.setattr("app.i18n.mt._gtx", boom)
    out = await translate("Rain 12.5 mm tomorrow.", "en", "brx")
    assert out.ok
    assert out.engine == "indictrans2"
    assert "via" not in out.engine
    assert out.tgt == "brx"
    assert "12.5" in out.text
    assert "बारिश" in out.text


@pytest.mark.asyncio
async def test_sidecar_down_bodo_routes_through_hindi(monkeypatch):
    import httpx

    async def post(path, payload):
        raise httpx.ConnectError("down")

    seen: list[tuple[str, str]] = []

    async def fake_gtx(text, src, tgt):
        seen.append((src, tgt))
        return MTResult(text="बारिश " + text, src=src, tgt=tgt, engine="google-gtx", ok=True)

    _patch_sidecar(monkeypatch, post)
    monkeypatch.setattr("app.i18n.mt._gtx", fake_gtx)
    monkeypatch.setattr("app.i18n.mt._mymemory", fake_gtx)
    out = await translate("Rain 12.5 mm tomorrow.", "en", "brx")
    assert out.ok
    assert out.engine.endswith(":via-hi")
    assert out.tgt == "hi"
    assert seen[-1][1] == "hi"
    assert "12.5" in out.text


@pytest.mark.asyncio
async def test_sidecar_skips_french(monkeypatch):
    made = {"n": 0}

    async def post(path, payload):
        made["n"] += 1
        raise AssertionError("french must not call the sidecar")

    seen: list[tuple[str, str]] = []

    async def fake_gtx(text, src, tgt):
        seen.append((src, tgt))
        return MTResult(text="Hello from France.", src="fr", tgt="en", engine="google-gtx", ok=True)

    client_made = _patch_sidecar(monkeypatch, post)
    monkeypatch.setattr("app.i18n.mt._gtx", fake_gtx)
    monkeypatch.setattr("app.i18n.mt._mymemory", fake_gtx)
    out = await translate("bonjour le monde", "fr", "en")
    assert out.ok
    assert out.engine == "google-gtx"
    assert seen[0] == ("fr", "en")
    assert made["n"] == 0
    assert client_made["n"] == 0


@pytest.mark.asyncio
async def test_sidecar_failed_piece_does_not_mix_with_gtx(monkeypatch):
    import httpx

    calls = {"n": 0}

    async def post(path, payload):
        calls["n"] += 1
        if calls["n"] == 2:
            raise httpx.ConnectError("down")
        return _Resp("বৃষ্টি " + payload["text"])

    gtx_calls: list[str] = []

    async def fake_gtx(text, src, tgt):
        gtx_calls.append(text)
        return MTResult(text="বৃষ্টি " + text, src=src, tgt=tgt, engine="google-gtx", ok=True)

    _patch_sidecar(monkeypatch, post)
    monkeypatch.setattr("app.i18n.mt._gtx", fake_gtx)
    monkeypatch.setattr("app.i18n.mt._mymemory", fake_gtx)
    out = await translate("Rain 1.5 mm today. More rain 2.5 mm tomorrow.", "en", "bn")
    assert out.ok
    assert out.engine == "google-gtx"
    assert len(gtx_calls) == 1
    assert out.text.count("বৃষ্টি") == 1
    assert "1.5" in out.text
    assert "2.5" in out.text


@pytest.mark.asyncio
@pytest.mark.skipif(not os.environ.get("RAINFALL_LIVE_MT"), reason="set RAINFALL_LIVE_MT=1 to hit Google")
async def test_live_google_roundtrip():
    inn = await inbound("হলদিয়ায় বায়ুর মান কেমন?", "en")
    assert inn.ok
    assert "Haldia" in inn.text or "haldia" in inn.text.lower()
    draft = "Haldia: CPCB AQI 47. Next 3 days 18.2 mm rain."
    out = await outbound(draft, "bn")
    assert out.ok
    assert has_script(out.text, "bn")
    assert "47" in out.text
    assert "18.2" in out.text
    assert "CPCB" in out.text

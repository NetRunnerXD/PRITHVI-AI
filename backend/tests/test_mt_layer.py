import os

import pytest

from app import cache
from app.i18n.detect import detect_lang, has_script, pick_output_locale, script_of
from app.i18n.mt import MTResult, inbound, outbound, protect, restore, translate


@pytest.fixture(autouse=True)
def _clear_mt_cache():
    cache.clear()
    yield
    cache.clear()


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
    # Bengali / Hindi typed into an English UI → reply in that language
    assert pick_output_locale(output_locale="en", locale_hint="en", detected="bn") == "bn"
    assert pick_output_locale(output_locale="en", locale_hint="en", detected="hi") == "hi"
    # explicit Reply-in override wins
    assert pick_output_locale(output_locale="hi", locale_hint="en", detected="bn") == "hi"
    assert pick_output_locale(output_locale="en", locale_hint="bn", detected="bn") == "en"
    # English typed in a Bengali UI stays on the UI reply language
    assert pick_output_locale(output_locale="bn", locale_hint="bn", detected="en") == "bn"
    # Tamil (or any other language) typed in an English UI comes back in Tamil
    assert pick_output_locale(output_locale="en", locale_hint="en", detected="ta") == "ta"
    assert pick_output_locale(output_locale="auto", locale_hint="en", detected="ta") == "ta"
    assert pick_output_locale(output_locale="auto", locale_hint="hi", detected="en") == "en"


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

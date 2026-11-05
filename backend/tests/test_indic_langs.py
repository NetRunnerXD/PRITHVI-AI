"""Per-language checks for the 22 scheduled languages plus Hinglish.

Fixtures (tests/fixtures/indic_langs.json) hold three weather questions per language and,
where Google covers it, a real translated reply with figures. Offline by default; set
PRITHVI_LIVE_MT=1 to also run every language through the live translation route.
"""

from __future__ import annotations

import json
import os
import re
import unicodedata
from pathlib import Path

import pytest

from app.i18n import mt
from app.i18n.detect import SCRIPT_FAMILY, detect_lang, has_script, is_hinglish, script_of
from app.i18n.mt import MTResult, VIA

FIX = json.loads((Path(__file__).parent / "fixtures" / "indic_langs.json").read_text(encoding="utf-8"))
SCHEDULED = [
    "as", "bn", "brx", "doi", "gu", "hi", "kn", "ks", "kok", "mai", "ml",
    "mni", "mr", "ne", "or", "pa", "sa", "sat", "sd", "ta", "te", "ur",
]
# Languages whose script alone identifies them (no pick needed).
OWN_SCRIPT = {"as", "gu", "kn", "ml", "mni", "or", "pa", "sat", "sd", "ta", "te", "ur", "hinglish"}
REPLY_EN = "Expect 12.5 mm of rain and 31 °C at 3 pm. AQI is 148."
FIGURES = ("12.5", "31", "148")


def _ascii_digits(text: str) -> str:
    return "".join(str(unicodedata.digit(ch)) if ch.isdigit() and not ch.isascii() else ch for ch in text)


def test_fixture_covers_all_22_plus_hinglish():
    assert set(SCHEDULED) | {"hinglish"} <= set(FIX)
    assert len(SCHEDULED) == 22


@pytest.mark.parametrize("lang", SCHEDULED + ["hinglish"])
def test_picked_language_wins_inside_its_script(lang):
    for q in FIX[lang]["questions"]:
        assert detect_lang(q, hint="hi", picked=lang) == lang, q


@pytest.mark.parametrize("lang", sorted(OWN_SCRIPT))
def test_script_alone_identifies(lang):
    for q in FIX[lang]["questions"]:
        assert detect_lang(q) == lang, q


@pytest.mark.parametrize("lang", ["kok", "mai", "sa", "doi", "brx"])
def test_shared_devanagari_never_forced_to_hindi_when_picked(lang):
    q = FIX[lang]["questions"][0]
    assert script_of(q) == "hi"
    assert detect_lang(q, hint="hi", picked=lang) == lang
    # Without a pick we stay in the Devanagari family.
    assert detect_lang(q) in SCRIPT_FAMILY["hi"]


def test_ol_chiki_and_meetei_mayek_scripts():
    assert script_of(FIX["sat"]["questions"][0]) == "sat"
    assert script_of(FIX["mni"]["questions"][0]) == "mni"


def test_kashmiri_and_sindhi_marks():
    assert detect_lang(FIX["sd"]["questions"][0]) == "sd"
    assert detect_lang(FIX["ks"]["questions"][0]) == "ks"
    assert detect_lang(FIX["ur"]["questions"][0]) == "ur"


def test_hinglish_detection_is_conservative():
    for q in FIX["hinglish"]["questions"]:
        assert is_hinglish(q), q
    for q in ("Will it rain in Patna tomorrow?", "What is the AQI in Delhi now?", "Haldia"):
        assert not is_hinglish(q), q
        assert detect_lang(q) != "hinglish"


@pytest.mark.parametrize("lang", [l for l in SCHEDULED + ["hinglish"] if FIX[l].get("reply")])
def test_reply_fixture_script_and_numbers(lang):
    reply = FIX[lang]["reply"]
    assert has_script(reply, lang)
    flat = _ascii_digits(reply)
    for fig in FIGURES:
        assert fig in flat, (lang, fig, reply)


def test_google_codes_for_weak_languages():
    assert mt._google_code("mni") == "mni-Mtei"
    assert VIA == {"brx": "hi", "ks": "ur"}


@pytest.fixture
def fake_gtx(monkeypatch):
    """Offline engine: prefix a native word, keep the number locks intact."""
    seen: list[tuple[str, str]] = []
    word = {l: FIX[l]["questions"][0].split()[0] for l in FIX}
    word["hi"] = "कल"

    async def _fake(text, src, tgt):
        seen.append((src, tgt))
        if tgt == "en":
            return MTResult(text="rain tomorrow?", src="hi", tgt="en", engine="fake", ok=True)
        return MTResult(text=f"{word.get(tgt, 'x')} {text}", src=src, tgt=tgt, engine="fake", ok=True)

    async def _no_mm(*_a, **_k):
        return None

    monkeypatch.setattr(mt, "_gtx", _fake)
    monkeypatch.setattr(mt, "_mymemory", _no_mm)
    mt.cache.clear()
    return seen


@pytest.mark.asyncio
@pytest.mark.parametrize("lang", SCHEDULED + ["hinglish"])
async def test_outbound_keeps_figures_and_routes(lang, fake_gtx):
    out = await mt.outbound(REPLY_EN + f" [{lang}]", lang)
    assert out.ok, out
    flat = _ascii_digits(out.text)
    for fig in FIGURES:
        assert fig in flat, (lang, out.text)
    if lang in VIA:
        assert out.tgt == VIA[lang]
        assert fake_gtx[-1][1] == VIA[lang]
        assert out.engine.endswith(f":via-{VIA[lang]}")
    elif lang == "hinglish":
        assert script_of(out.text) is None
        assert out.engine.endswith("+romanize")
    else:
        assert has_script(out.text, lang)


@pytest.mark.asyncio
async def test_inbound_bodo_goes_auto_not_hindi(fake_gtx):
    q = FIX["brx"]["questions"][0]
    res = await mt.inbound(q, hint="hi", picked="brx")
    assert res.ok and res.src == "brx"
    assert fake_gtx[-1] == ("auto", "en")


LIVE = os.getenv("PRITHVI_LIVE_MT") == "1"


@pytest.mark.skipif(not LIVE, reason="set PRITHVI_LIVE_MT=1 for the live route")
@pytest.mark.asyncio
@pytest.mark.parametrize("lang", SCHEDULED + ["hinglish"])
async def test_live_outbound(lang):
    out = await mt.outbound(REPLY_EN, lang)
    assert out.ok, out
    assert has_script(out.text, VIA.get(lang, lang))
    flat = _ascii_digits(out.text)
    for fig in FIGURES:
        assert fig in flat, (lang, out.text)

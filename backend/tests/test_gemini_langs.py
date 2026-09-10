from app.i18n.gemini_langs import gemini_native


def test_gemini_covers_major_indic():
    for lang in ("hi", "bn", "ta", "te", "kn", "ml", "gu", "pa", "or", "as", "mr", "ur", "ne"):
        assert gemini_native(lang), lang


def test_gemini_skips_weak_eighth_schedule():
    for lang in ("sat", "brx", "doi", "ks", "sa", "mni", "kok", "mai"):
        assert not gemini_native(lang), lang


def test_gemini_english():
    assert gemini_native("en")

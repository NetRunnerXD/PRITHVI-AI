from app.providers.imd import clean_cap_body, humanize_cap_title, severity_from_title


def test_humanize_stacked_heavy_phrase():
    out = humanize_cap_title("Heavy to very heavy with extremely heavy rainfall", place="Nadia")
    assert out == "Extremely heavy rainfall warning — Nadia"
    assert "to very heavy with" not in out.lower()
    assert severity_from_title(out) == "extreme"


def test_humanize_plain_heavy():
    out = humanize_cap_title("Heavy rainfall warning for Gangetic West Bengal", place="Kolkata")
    assert out.startswith("Heavy rainfall warning")
    assert "Kolkata" in out


def test_clean_cap_body_drops_stacked_intensity():
    raw = "Heavy to very heavy with extremely heavy rainfall"
    body = (
        "Heavy to very heavy with extremely heavy rainfall. "
        "Extremely Heavy Rainfall at isolated places over Gangetic West Bengal. "
        "Valid from 19 Aug 2026 08:30 IST."
    )
    out = clean_cap_body(body, title="Extremely heavy rainfall warning — Nadia", raw_title=raw)
    assert "to very heavy with" not in out.lower()
    assert "extremely heavy rainfall at" not in out.lower()
    assert "Valid from 19 Aug" in out

from app.i18n.number_lock import allowed_from_tools, ungrounded
from app.i18n.templates import render
from app.agents.intent_router import classify


def test_ungrounded_detected():
    allowed = allowed_from_tools([{"precip_next_3d_mm": 47.2, "liters": 800}])
    bad = ungrounded("Rain is 47.2 mm and also 9999 liters", allowed)
    assert "9999" in bad
    assert "47.2" not in bad
    # years and tiny counts are harmless; invented percents/scores are not
    assert "82" in ungrounded("In 2026 the top 5 districts score 82", allowed)


def test_bn_template_keeps_numbers():
    text = render(
        "irrigation_hold_rain",
        "bn",
        {
            "days": 3,
            "intensity": "moderate to heavy",
            "rain_mm": 47.2,
            "prob": 78,
            "liters_min": 800,
            "liters_max": 1200,
        },
    )
    assert "47.2" in text
    assert "800" in text
    assert "1200" in text
    assert "বৃষ্টি" in text


def test_intent_bengali_irrigation():
    q = "আগামী তিন দিনে আমার এলাকায় বৃষ্টির সম্ভাবনা কেমন? এখন সেচ দেওয়া উচিত কি?"
    assert classify(q) == "irrigation"

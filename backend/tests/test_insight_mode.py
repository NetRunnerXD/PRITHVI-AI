from app.agents.insight_compiler import finish_insight_body, length_body
from app.agents.post import DANGER_AQI, severity
from app.schemas.insight import Band, InsightPacket
from app.schemas.location import Location


def test_length_body_max_three_sentences():
    t = "One. Two. Three. Four extra."
    out = length_body(t)
    assert out.count(".") <= 3
    assert "Four" not in out


def test_finish_template_on_bad_json():
    loc = Location(id="x", label="Haldia", state="West Bengal", district="Purba Medinipur", lat=22, lon=88)
    pkt = InsightPacket(
        locus="Haldia",
        generated_at="t",
        pack_fingerprint="p",
        bands=[
            Band(key="aqi_now", scale="cpcb", category="Poor", band="poor", meaning="Air is poor for outdoor work and children.")
        ],
        actions=["Limit outdoor field work."],
    )
    body, src = finish_insight_body("not json at all 99999", pkt, {}, "AQI?")
    assert src == "template"
    assert "poor" in body.lower() or "Limit" in body


def test_safety_footer_not_in_body_eval():
    collected = {"aqi": {"cpcb": {"value": 220}}}
    text = "Air is poor. Stay inside."
    out = severity(text, collected)
    assert DANGER_AQI in out
    body = out.split(DANGER_AQI)[0].strip()
    assert body.count(".") <= 3

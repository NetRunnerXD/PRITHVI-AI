from app.agents.insight_compiler import (
    compile_insight,
    insight_canary,
    insight_eligible,
    parse_insight_reply,
    us_epa_aqi_category,
)
from app.providers.datagov import aqi_category
from app.schemas.location import Location


def _loc():
    return Location(
        id="x",
        label="Howrah, West Bengal",
        state="West Bengal",
        district="Howrah",
        lat=22.6,
        lon=88.3,
        place_name="Howrah",
    )


class _L1:
    intent = "aqi"
    sentiment = "inquisitive"
    tone = "worried"
    domain = "urban"


class _Gate:
    def __init__(self, needs, mode="data"):
        self.needs = needs
        self.mode = mode


class _Tri:
    def __init__(self, kind):
        self.kind = kind


class _Plan:
    catalog = False


def test_cpcb_151_is_moderate_not_unhealthy():
    assert aqi_category(151) == "Moderate"
    pkt = compile_insight(
        _loc(),
        {"aqi": {"need": "aqi", "cpcb": {"value": 151}, "om_us_aqi": None}},
        _L1(),
    )
    now = next(b for b in pkt.bands if b.key == "aqi_now")
    assert now.scale == "cpcb"
    assert now.category == "Moderate"
    assert now.band == "moderate"
    assert "151" in (now.raw_cite or "")


def test_epa_helper_151_is_unhealthy():
    label, band = us_epa_aqi_category(151)
    assert label == "Unhealthy"
    assert band == "unhealthy"


def test_epa_only_when_no_cpcb():
    pkt = compile_insight(
        _loc(),
        {"aqi": {"need": "aqi", "cpcb": None, "om_us_aqi": 151}},
        _L1(),
    )
    now = next(b for b in pkt.bands if b.key == "aqi_now")
    assert now.scale == "us_epa"
    assert now.category == "Unhealthy"


def test_rain_tie_break_heavy_wins():
    pkt = compile_insight(
        _loc(),
        {
            "nowcast": {"nowcast": {"mm_h": 5.0}, "actions": ["Stay off the bund."]},
            "forecast": {"precip_prob": [10]},
        },
        _L1(),
    )
    rain = next(b for b in pkt.bands if b.key == "rain_next_2h")
    assert rain.category == "heavy"


def test_rain_likely_from_prob():
    pkt = compile_insight(
        _loc(),
        {"forecast": {"precip_1h_mm": 0.0, "precip_prob": [70]}},
        _L1(),
    )
    rain = next(b for b in pkt.bands if b.key == "rain_next_2h")
    assert rain.category == "likely"


def test_flood_danger_band():
    pkt = compile_insight(
        _loc(),
        {"risks": {"need": "risks", "risks": [{"id": "flood", "score_pct": 80}]}},
        _L1(),
    )
    fl = next(b for b in pkt.bands if b.key == "flood")
    assert fl.band == "danger"
    assert fl.missing is False


def test_missing_aqi_does_not_invent_zero():
    pkt = compile_insight(_loc(), {"forecast": {"precip_1h_mm": 0.0}}, _L1())
    assert not any(b.key == "aqi_now" and not b.missing for b in pkt.bands)
    assert "aqi" in pkt.needs_extra


def test_kalman_stripped_from_packet():
    pkt = compile_insight(
        _loc(),
        {"nowcast": {"nowcast": {"mm_h": 0.1}, "playhead": 99, "kalman": {"x": 1}}},
        _L1(),
    )
    dump = pkt.model_dump_json()
    assert "playhead" not in dump


def test_insight_eligible_excludes_rank_emergency():
    l1 = _L1()
    l1.intent = "forecast"
    assert insight_eligible(l1, _Gate(["forecast"]), _Tri("data"), _Plan())
    assert not insight_eligible(l1, _Gate(["rank"]), _Tri("data"), _Plan())
    assert not insight_eligible(l1, _Gate(["forecast"]), _Tri("emergency"), _Plan())
    chat_plan = _Plan()
    assert not insight_eligible(l1, _Gate([]), _Tri("chat"), chat_plan)


def test_canary_sha256_no_anon_bucket():
    assert not insight_canary(None, 10, True)
    assert not insight_canary("", 10, True)
    assert insight_canary("abc", 100, True)
    assert not insight_canary("abc", 10, False)
    a = insight_canary("conv-1", 50, True)
    b = insight_canary("conv-1", 50, True)
    assert a is b


def test_parse_fenced_json():
    raw = 'Sure\n```json\n{"meaning": "Air is poor.", "suggestion": "Keep kids indoors."}\n```'
    obj = parse_insight_reply(raw)
    assert obj["meaning"].startswith("Air")

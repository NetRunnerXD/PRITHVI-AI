from datetime import date

from app.agents.dates import parse_window
from app.agents.intent_router import classify, mentioned_place, required_tools


def test_parse_23_to_28_august():
    w = parse_window(
        "Can you show me rainfall prediction in haldia for 23 to 28th August?",
        today=date(2026, 8, 18),
    )
    assert w is not None
    assert w["start"] == date(2026, 8, 23)
    assert w["end"] == date(2026, 8, 28)
    assert w["kind"] == "range"


def test_parse_iso_and_next_days():
    w = parse_window("rain 2026-08-23 to 2026-08-25", today=date(2026, 8, 18))
    assert w["start"].isoformat() == "2026-08-23"
    assert w["end"].isoformat() == "2026-08-25"
    n = parse_window("next 5 days rain", today=date(2026, 8, 18))
    assert n["start"] == date(2026, 8, 18)
    assert n["end"] == date(2026, 8, 22)


def test_window_intent_and_tools():
    q = "Can you show me rainfall prediction in haldia for 23 to 28th August?"
    assert classify(q) == "window"
    assert mentioned_place(q) == "Haldia"
    assert "get_rain_window" in required_tools("window")
    assert "get_rain_window" in required_tools("rain")


def test_single_day():
    w = parse_window("rain on 25 August", today=date(2026, 8, 18))
    assert w["start"] == date(2026, 8, 25)
    assert w["end"] == date(2026, 8, 25)


def test_tomorrow_today_weekend():
    today = date(2026, 8, 18)  # Tuesday
    tmr = parse_window("rain tomorrow", today=today)
    assert tmr["start"] == date(2026, 8, 19)
    assert tmr["kind"] == "day"
    tod = parse_window("AQI tonight", today=today)
    assert tod["start"] == today
    wk = parse_window("this weekend", today=today)
    assert wk["start"] == date(2026, 8, 22)
    assert wk["end"] == date(2026, 8, 23)
    # named range still wins over "today"
    rng = parse_window("today rain 23 to 28th August", today=today)
    assert rng["start"] == date(2026, 8, 23)
    assert rng["end"] == date(2026, 8, 28)

import asyncio

from app.agents.layer1_parser import detect_tone, parse_semantic_context


def test_tone_precedence_kids_asthma():
    assert detect_tone("Is the air bad for my kids with asthma?") == "worried"


def test_tone_health_aqi():
    assert detect_tone("What is the AQI in Howrah?") == "health"


def test_tone_hindi_worried():
    assert detect_tone("बच्चों के लिए सुरक्षित है?") == "worried"


def test_tone_farming_from_domain():
    assert detect_tone("Should I irrigate tomorrow?", domain="farming") == "farming"


def test_sentiment_buckets_unchanged():
    ctx = asyncio.run(parse_semantic_context("AQI pollution today in Howrah"))
    assert ctx.sentiment == "inquisitive"
    assert ctx.tone == "health"
    assert "Tone: health" in ctx.tailored_user_hint

    av = asyncio.run(parse_semantic_context("Is it safe to fly a drone in Haldia?"))
    assert av.sentiment == "operational_safety"
    assert av.domain == "aviation"


def test_layer1_named_hour_and_disaster_brief():
    hour = asyncio.run(parse_semantic_context("What is the forecast for Haldia tomorrow at 3 pm"))
    assert hour.time_window
    assert hour.time_window.get("hour") == "15"
    desk = asyncio.run(
        parse_semantic_context("NDRF desk: list warnings and flood risk at this pin for evacuation")
    )
    assert desk.domain == "disaster"
    assert "SITUATION" in desk.tailored_user_hint

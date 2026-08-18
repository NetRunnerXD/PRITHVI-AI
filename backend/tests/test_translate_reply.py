from app.agents.intent_router import mentioned_place
from app.i18n.translate_reply import compose_indic, translate_reply
from app.schemas.dashboard import (
    CurrentConditions,
    DashboardSnapshot,
    Descriptive,
    Diagnostic,
    MapState,
    Predictive,
    Prescriptive,
)
from app.schemas.location import Location
from app.schemas.risk import Prescription, Quant


def test_haldia_is_purba_medinipur():
    assert mentioned_place("Air quality in Haldia") == "Haldia"
    assert mentioned_place("Air quality in Tamluk") == "Tamluk"


def test_no_mid_sentence_splice():
    en = "To provide a more comprehensive view for other districts in West Bengal, based on the available data."
    bn = translate_reply(en, "bn")
    assert "জেলা —" not in bn
    assert "ভিত্তি —" not in bn
    assert bn == en  # free-form English is left alone


def test_compose_irrigation_bn():
    loc = Location(id="x", label="Darjeeling, West Bengal", state="West Bengal", district="Darjeeling", lat=27.0, lon=88.2)
    hold = Prescription(
        id="hold_irrigation",
        priority=1,
        action="hold",
        quant=Quant(water_saved_liters_min=800, water_saved_liters_max=1200),
    )
    snap = DashboardSnapshot(
        location=loc,
        generated_at="t",
        sources=[],
        descriptive=Descriptive(current=CurrentConditions(soil_moisture_m3m3=0.372)),
        diagnostic=Diagnostic(),
        predictive=Predictive(precip_next_3d_mm=18.2),
        prescriptive=Prescriptive(actions=[hold]),
        risks=[],
        map=MapState(center=[27.0, 88.2]),
    )
    text = compose_indic("bn", "irrigation", snap, {})
    assert text
    assert "18.2" in text
    assert "সেচ" in text
    assert "জেলা —" not in text
    assert "আগামী ৩ দিনে আনুমানিক" in text


def test_compose_general_and_outlook_have_script():
    from app.i18n.detect import has_script

    loc = Location(id="x", label="Nadia, West Bengal", state="West Bengal", district="Nadia", lat=23.4, lon=88.5)
    snap = DashboardSnapshot(
        location=loc,
        generated_at="t",
        sources=[],
        descriptive=Descriptive(current=CurrentConditions(temp_c=26.5, sky_label="Thunderstorm", aqi=47)),
        diagnostic=Diagnostic(),
        predictive=Predictive(precip_next_3d_mm=54.0, precip_7d_mm=80.0, water_balance_7d_mm=20.0),
        prescriptive=Prescriptive(),
        risks=[],
        map=MapState(center=[23.4, 88.5]),
    )
    bn = compose_indic("bn", "general", snap, {})
    hi = compose_indic("hi", "outlook", snap, {})
    assert bn and has_script(bn, "bn") and "54.0" in bn
    assert hi and has_script(hi, "hi") and "80.0" in hi

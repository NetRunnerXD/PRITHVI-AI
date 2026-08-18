import pytest

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
from app.schemas.risk import RiskCard
from app.tools import build_registry


def _snap() -> DashboardSnapshot:
    loc = Location(
        id="in_wb_nadia",
        label="Nadia, West Bengal",
        state="West Bengal",
        district="Nadia",
        lat=23.47,
        lon=88.55,
    )
    flood = RiskCard(
        id="flood",
        label="Flood Risk",
        severity="medium",
        score_pct=54,
        confidence_pct=90,
        factors=[],
        updated_at="2026-08-17T00:00:00Z",
    )
    return DashboardSnapshot(
        location=loc,
        generated_at="2026-08-17T00:00:00Z",
        sources=["open-meteo"],
        descriptive=Descriptive(current=CurrentConditions(temp_c=28, soil_moisture_m3m3=0.3, aqi=47)),
        diagnostic=Diagnostic(),
        predictive=Predictive(
            precip_next_3d_mm=50,
            precip_7d_mm=70,
            water_balance_7d_mm=20,
            outlook_days=[{"date": "2026-08-17", "precip_mm": 30, "irrigate": False}],
        ),
        prescriptive=Prescriptive(),
        risks=[flood],
        map=MapState(center=[23.47, 88.55]),
        ogd={"mandi": [{"commodity": "Rice", "modal_price": 4900}]},
    )


@pytest.mark.asyncio
async def test_registry_core_tools():
    reg = build_registry(_snap())
    names = set(reg.tools)
    for n in (
        "get_weather_forecast",
        "get_7day_outlook",
        "get_water_balance",
        "compare_districts",
        "switch_location",
        "explain_risk",
        "get_mandi_prices",
        "rank_districts",
        "list_districts",
        "get_state_mandi",
        "get_nowcast",
    ):
        assert n in names
    fc = await reg.call("get_weather_forecast", {"days": 3})
    assert fc["precip_next_3d_mm"] == 50
    wb = await reg.call("get_water_balance", {})
    assert wb["water_balance_7d_mm"] == 20
    risk = await reg.call("explain_risk", {"risk_id": "flood"})
    assert risk["risk"]["score_pct"] == 54
    mandi = await reg.call("get_mandi_prices", {})
    assert mandi["mandi"][0]["commodity"] == "Rice"
    hz = await reg.call("get_hazard_watch", {})
    assert "live" in hz
    assert "warnings" in hz


def test_openai_schemas_are_functions():
    schemas = build_registry(_snap()).openai_schemas()
    assert all(s["type"] == "function" for s in schemas)
    assert {s["function"]["name"] for s in schemas} >= {"get_7day_outlook", "switch_location"}

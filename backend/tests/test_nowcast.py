from datetime import datetime
from types import SimpleNamespace

import pytest

from app.science.nowcast import (
    apply_speech_only,
    blend_hours,
    build,
    cap_prior,
    fuse_speech,
    neighbor_storm,
    ponding,
    pump_regret,
    regime,
    split_hours,
    state_vector,
)
from app.tools import build_registry
from app.agents.intent_router import required_tools
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


def _loc(**over):
    base = dict(district="Nadia", lat=23.47, lon=88.56, place_kind="district", place_name="Nadia")
    base.update(over)
    return SimpleNamespace(**base)


def _feat(**over):
    f = {
        "hourly_times": [f"2026-08-18T{h:02d}:00" for h in range(10, 20)],
        "hourly_precip": [0.0, 0.2, 1.4, 3.2, 2.1, 0.8, 0.3, 0.1, 0.0, 0.0],
        "hourly_cloud": [40, 55, 70, 80, 75, 60],
        "hourly_wind_dir": [180, 200, 240, 250],
        "hourly_rh": [70, 72, 78, 82, 80, 76],
        "hourly_temp": [34, 33, 32, 31, 30, 29],
        "hourly_prob": [20, 40, 70, 80, 60, 40, 20, 10, 10, 10],
        "hourly_us_aqi": [90, 100, 110, 120, 115, 100],
        "hourly_aqi_times": [f"2026-08-18T{h:02d}:00" for h in range(10, 16)],
        "precip_today_mm": 8,
        "precip_3d_mm": 20,
        "precip_z": 0.4,
        "daily_times": ["2026-08-18"],
        "temp_max": [34],
        "rh_now": 72,
        "naqi": 110,
        "visibility_m": 4000,
        "weather_code": 95,
        "coast_km": 80,
        "wave_height_m": 0.6,
        "discharge_trend": "steady",
    }
    f.update(over)
    return f


def test_split_and_engines(monkeypatch):
    from datetime import datetime
    from app.science import nowcast as nc

    monkeypatch.setattr(nc, "_now", lambda: datetime(2026, 8, 18, 12, 5, tzinfo=nc.IST))
    f = _feat()
    past, future = split_hours(f["hourly_times"], f["hourly_precip"])
    assert past[-1]["mm"] == 1.4
    assert future[0]["mm"] == 3.2
    st = state_vector(f)
    reg = regime(past, f, st, 23.47)
    hours = blend_hours(past, future, reg, {"upstream_mm": None}, 0.0, cap_prior([], False), [70, 80, 60, 40, 20, 10])
    assert hours[0]["engine"] == "nowcast"
    assert hours[1]["engine"] == "nowcast"
    assert hours[2]["engine"] == "blend"
    assert hours[4]["engine"] == "nwp"
    assert hours[0]["mm"] >= 0


def test_speech_does_not_change_millimetres(monkeypatch):
    from datetime import datetime
    from app.science import nowcast as nc

    monkeypatch.setattr(nc, "_now", lambda: datetime(2026, 8, 18, 12, 5, tzinfo=nc.IST))
    hy = {"memory": 0.5, "limb": "wetting", "flip": "runoff"}
    pack = build(_feat(), _loc(), hy=hy, ph={"stage": "tillering", "stage_score": 0.7})
    mm0 = [h["mm"] for h in pack["hours"]]
    fused = apply_speech_only(pack, "কালবৈশাখী ঝমাঝম")
    assert [h["mm"] for h in fused["hours"]] == mm0
    assert fused["speech"]["mm_changed"] is False
    assert "squall" in fused["speech"]["heard"]["tags"] or "heavy_rain" in fused["speech"]["heard"]["tags"]


def test_cap_does_not_invent_rain(monkeypatch):
    from app.science import nowcast as nc

    dry = {
        "hourly_times": [f"2026-08-18T{h:02d}:00" for h in range(10, 18)],
        "hourly_precip": [0.0] * 8,
        "hourly_cloud": [10, 10, 10, 10],
        "hourly_wind_dir": [90, 90],
        "hourly_rh": [40, 40, 40, 40],
        "hourly_temp": [30, 30, 30, 30],
        "precip_today_mm": 0,
        "precip_3d_mm": 1,
        "precip_z": -1,
        "daily_times": ["2026-08-18"],
        "temp_max": [31],
        "rh_now": 40,
    }
    monkeypatch.setattr(nc, "_now", lambda: datetime(2026, 8, 18, 12, 0, tzinfo=nc.IST))
    hy = {"memory": 0.2, "limb": "drying", "flip": "absorbing"}
    pack = build(
        dry,
        _loc(),
        hy=hy,
        cap_hit=True,
        caps=[{"title": "Thunderstorm warning", "body": "next 3 hours heavy thunder"}],
    )
    assert all(h["mm"] == 0 for h in pack["hours"])
    assert pack["cap"]["thunder"] is True
    assert pack["cap"]["note"]


def test_wet_limb_ponds_more():
    hours = [{"t": "t1", "mm": 8.0, "lead_h": 1, "engine": "nowcast", "p_wet": 0.8}]
    wet = ponding(hours, {"memory": 0.8, "limb": "wetting", "flip": "runoff"})
    dry = ponding(hours, {"memory": 0.1, "limb": "drying", "flip": "absorbing"})
    assert wet["mm_60"] > dry["mm_60"]


def test_pump_hold_when_rain_is_on():
    hours = [
        {"t": "t1", "mm": 2.4, "lead_h": 1, "engine": "nowcast", "p_wet": 0.7},
        {"t": "t2", "mm": 1.8, "lead_h": 2, "engine": "nowcast", "p_wet": 0.6},
    ]
    pump = pump_regret(hours, 400.0, {"memory": 0.6})
    assert pump["action"] == "hold"
    assert pump["liters_at_risk"] > 0


def test_neighbor_disagreement_flag(monkeypatch):
    from app.science import nowcast as nc

    past = [{"t": "t", "mm": 0.0}]
    neighbors = [
        {"hourly_times": ["2026-08-18T11:00"], "hourly_precip": [2.0]},
        {"hourly_times": ["2026-08-18T11:00"], "hourly_precip": [1.5]},
        {"hourly_times": ["2026-08-18T11:00"], "hourly_precip": [0.0]},
    ]
    monkeypatch.setattr(nc, "_now", lambda: datetime(2026, 8, 18, 12, 0, tzinfo=nc.IST))
    flag = neighbor_storm(neighbors, past)
    assert flag["flag"] is True
    assert flag["wet_neighbors"] >= 2


def test_locked_json_and_build(monkeypatch):
    from datetime import datetime
    from app.science import nowcast as nc

    monkeypatch.setattr(nc, "_now", lambda: datetime(2026, 8, 18, 12, 5, tzinfo=nc.IST))
    pack = build(
        _feat(),
        _loc(),
        hy={"memory": 0.6, "limb": "wetting", "flip": "runoff"},
        ph={"stage": "transplant", "stage_score": 0.88},
        neighbors=[
            {
                "id": "a",
                "district": "North 24 Parganas",
                "lat": 22.8,
                "lon": 88.6,
                "hourly_times": [f"2026-08-18T{h:02d}:00" for h in range(10, 16)],
                "hourly_precip": [4, 3, 2, 1, 0, 0],
            },
            {
                "id": "b",
                "district": "Murshidabad",
                "lat": 24.2,
                "lon": 88.2,
                "hourly_times": [f"2026-08-18T{h:02d}:00" for h in range(10, 16)],
                "hourly_precip": [0.2, 0.1, 0, 0, 0, 0],
            },
        ],
    )
    lock = pack["locked"]
    for key in (
        "hours",
        "onset",
        "p_interrupt_90m",
        "liters_at_risk",
        "enterable_2h",
        "regime",
        "engine_note",
    ):
        assert key in lock
    assert pack["advection"]["n"] == 2
    assert pack["place"]["name"] == "Nadia"
    assert pack["air"]["peak_us_aqi"] is not None
    assert pack["split"]["pluvial"] in {True, False}
    assert pack["speech"]["mm_changed"] is False


def test_fuse_speech_category_only():
    kal = {"score_pct": 40, "level": "quiet"}
    out = fuse_speech("কালবৈশাখী", kal)
    assert out["mm_changed"] is False
    assert out["onset_pull"] is True
    assert kal["level"] in {"watch", "quiet"}


@pytest.mark.asyncio
async def test_get_nowcast_tool_and_intent():
    assert "get_nowcast" in required_tools("rain")
    assert "get_nowcast" in required_tools("irrigation")
    loc = Location(id="in_wb_nadia", label="Nadia", state="West Bengal", district="Nadia", lat=23.47, lon=88.56)
    snap = DashboardSnapshot(
        location=loc,
        generated_at="2026-08-18T00:00:00Z",
        sources=["open-meteo"],
        descriptive=Descriptive(current=CurrentConditions(temp_c=28)),
        diagnostic=Diagnostic(),
        predictive=Predictive(),
        prescriptive=Prescriptive(),
        risks=[],
        map=MapState(center=[23.47, 88.56]),
        science={
            "nowcast": {
                "locked": {"hours": [{"t": "2026-08-18T13:00", "lead_h": 1, "mm": 1.2, "engine": "nowcast"}], "p_interrupt_90m": 0.6},
                "hours": [{"t": "2026-08-18T13:00", "lead_h": 1, "mm": 1.2, "engine": "nowcast"}],
                "kal": {"score_pct": 40, "level": "quiet"},
                "cap": {},
                "pump": {"p_interrupt_90m": 0.6, "action": "hold", "liters_at_risk": 200},
                "access": {"enterable": False},
                "speech": {"heard": {"tags": []}, "onset_pull": False, "p_interrupt_delta": 0, "mm_changed": False},
            }
        },
    )
    reg = build_registry(snap)
    assert "get_nowcast" in reg.tools
    out = await reg.call("get_nowcast", {})
    assert out["nowcast"]["p_interrupt_90m"] == 0.6
    assert out["nowcast"]["hours"][0]["mm"] == 1.2

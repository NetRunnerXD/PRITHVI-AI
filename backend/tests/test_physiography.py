from datetime import datetime
from types import SimpleNamespace

from app.data.cwc_wb import nearest
from app.data.physiography import classify, hugli_relevant
from app.science.live import playhead
from app.science.nowcast import IST, kal_baisakhi, ponding, tide_rain
from app.services.locality import port_relevant
from app.services.location_svc import resolve_named_place


def test_hugli_only_for_estuary():
    assert hugli_relevant(22.07, 88.07, place="Haldia")
    assert hugli_relevant(loc=SimpleNamespace(state="West Bengal", district="Howrah", place_name="Howrah", lat=22.59, lon=88.31))
    assert not hugli_relevant(26.91, 70.91, state="Rajasthan", district="Jaisalmer", place="Jaisalmer")
    assert not hugli_relevant(26.91, 75.79, state="Rajasthan", district="Jaipur", place="Jaipur")
    assert not hugli_relevant(34.15, 77.58, state="Ladakh", district="Leh", place="Leh")
    jaipur = resolve_named_place("Jaipur")
    assert jaipur is not None
    assert not port_relevant(jaipur)
    haldia = resolve_named_place("Haldia")
    assert haldia is not None
    assert port_relevant(haldia)


def test_kinds_desert_hills_delta():
    assert classify(26.91, 70.91, district="Jaisalmer", state="Rajasthan")["kind"] == "arid"
    assert classify(34.15, 77.58, district="Leh", state="Ladakh")["kind"] == "orographic"
    assert classify(22.07, 88.07, place="Haldia", state="West Bengal", district="Purba Medinipur")["kind"] == "hugli"
    pune = classify(18.52, 73.86, district="Pune", state="Maharashtra")
    assert pune["kind"] in {"plateau", "plains"}
    assert not pune["show_tide"]


def test_arid_ponds_less_than_delta():
    hours = [{"t": "t1", "mm": 8.0, "lead_h": 1, "engine": "nowcast", "p_wet": 0.8}]
    hy = {"memory": 0.8, "limb": "wetting", "flip": "runoff"}
    delta = ponding(hours, hy, {"pond_scale": 1.0, "kind": "hugli"})
    desert = ponding(hours, hy, {"pond_scale": 0.18, "kind": "arid"})
    hills = ponding(hours, hy, {"pond_scale": 0.35, "kind": "orographic"})
    assert desert["mm_60"] < hills["mm_60"] < delta["mm_60"]


def test_kal_not_from_afternoon_in_desert():
    f = {"hourly_temp": [38, 37, 36, 34], "weather_code": 1}
    st = {"rh_jump": 10, "cloud_jump": 25, "wind_shift_deg": 50}
    past = [{"mm": 1.2}]
    now = datetime(2026, 8, 18, 15, 0, tzinfo=IST)
    arid = kal_baisakhi(f, past, st, now=now, phys={"kal_belt": False})
    belt = kal_baisakhi(f, past, st, now=datetime(2026, 4, 18, 15, 0, tzinfo=IST), phys={"kal_belt": True})
    assert arid["level"] == "quiet"
    assert arid["kal_belt"] is False
    assert belt["level"] == "watch"
    thunder = kal_baisakhi({"weather_code": 95}, [], {}, now=now, phys={"kal_belt": False})
    assert thunder["level"] == "watch"


def test_tide_hidden_off_hugli():
    hours = [{"mm": 5}, {"mm": 2}, {"mm": 1}]
    off = tide_rain(hours, 5, 75.8, 2.0, phys={"show_tide": False, "hugli": False})
    on = tide_rain(hours, 5, 88.07, 2.0, phys={"show_tide": True, "hugli": True})
    assert off["relevant"] is False
    assert off["drain_blocked"] is False
    assert off["stay_off_ghat"] is False
    assert on["relevant"] is True


def test_cwc_hidden_when_far():
    haldia = nearest(22.07, 88.07)
    desert = nearest(26.91, 70.91)
    pune = nearest(18.52, 73.86)
    assert haldia["relevant"] is True
    assert haldia["name"] == "Haldia"
    assert desert["relevant"] is False
    assert pune["relevant"] is True
    assert pune["name"] == "Pune"


def test_playhead_no_hugli_metres_in_jaipur():
    hours = [{"t": "2026-08-18T13:00:00", "mm": 1.2, "lead_h": 1, "engine": "nowcast", "p_wet": 0.5}]
    from app.science.live import gap_series

    pack = {
        "hours": hours,
        "gap": gap_series(hours),
        "clock": {"t_start": "2026-08-18T13:20:00"},
        "ponding": {"factor": 0.1},
        "place": {"name": "Jaipur", "district": "Jaipur", "lat": 26.91, "lon": 75.79},
        "phys": {"show_tide": False, "kind": "plateau"},
    }
    loc = SimpleNamespace(state="Rajasthan", district="Jaipur", place_name="Jaipur", lat=26.91, lon=75.79)
    ph = playhead(pack, now=datetime(2026, 8, 18, 13, 10, tzinfo=IST), loc=loc)
    assert ph["tide_relevant"] is False
    assert ph["tide_m"] is None

from datetime import datetime, timedelta

from app.science.nowcast import IST
from app.science.sat_phys import blend, code_class, drivers_from_features, r_phys, schedule_pulses


def _drv():
    t0 = datetime(2026, 8, 18, 8, 0, tzinfo=IST)
    times = []
    precip, cloud, rh, cape, code = [], [], [], [], []
    for i in range(6):
        t = t0 + timedelta(hours=i)
        times.append(t.isoformat(timespec="seconds"))
        precip.append(0.2 if i < 2 else 1.8)
        cloud.append(40.0 + 12 * i)
        rh.append(68.0 + 4 * i)
        cape.append(200.0 + 250 * i)
        code.append(3 if i < 2 else 95)
    loc = type("L", (), {"lat": 22.07, "lon": 88.07})()
    f = {
        "hourly_times": times,
        "hourly_precip": precip,
        "hourly_cloud": cloud,
        "hourly_rh": rh,
        "hourly_cape": cape,
        "hourly_weather_code": code,
        "hourly_temp": [32] * 6,
        "hourly_dew": [26] * 6,
        "coast_km": 2,
    }
    pack = {
        "regime": {"name": "cell"},
        "advection": {"upstream_mm": 2.4, "speed_kmh": 18},
        "stream": {"eta_h": 0.4},
        "kal": {"level": "watch"},
        "neighbor_storm": {"wet_neighbors": 2},
    }
    return drivers_from_features(f, loc, pack)


def test_thunder_is_not_a_flat_bar():
    drv = _drv()
    pulses = schedule_pulses(drv)
    assert pulses
    t0 = datetime(2026, 8, 18, 12, 0, tzinfo=IST)
    rates = [r_phys(t0 + timedelta(seconds=s), drv, pulses)["r"] for s in range(0, 3600, 60)]
    assert max(rates) - min(rates) > 0.35
    # Not a monotone ramp (would look like a bar between two hours).
    mid = rates[len(rates) // 2]
    assert mid != rates[0] or mid != rates[-1]


def test_blend_adds_pulse_on_top_of_envelope():
    phys = {"mod": 1.1, "pulse": 0.8, "adv": 0.2}
    r = blend(1.0, phys)
    assert r > 1.0
    assert r >= 1.1 + 0.5


def test_code_class_from_precip_if_missing():
    assert code_class(95, 0)[0] == "thunder"
    assert code_class(None, 5.0)[0] == "cell"
    assert code_class(None, 0.0)[0] == "dry"

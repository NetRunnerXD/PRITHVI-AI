from app.agents.counterfactual import detect_scale, scale_forecast
from app.agents.ledger import hash_pack, ledger_for


def test_detect_double_rain():
    assert detect_scale("what if rainfall doubles tomorrow") == 2.0
    assert detect_scale("what if 3x rain") == 3.0
    assert detect_scale("what if 1000x rain") is None


def test_scale_forecast_precip_only():
    pack = {
        "need": "forecast",
        "precip_next_3d_mm": 10,
        "temp_c": 30,
        "outlook_days": [{"date": "2026-08-30", "precip_mm": 5, "soil_m3m3": 0.2, "irrigate": True}],
    }
    out = scale_forecast(pack, 2.0)
    assert out["precip_next_3d_mm"] == 20
    assert out["temp_c"] == 30
    assert out["outlook_days"][0]["precip_mm"] == 10
    assert out["counterfactual_scale"] == 2.0


def test_ledger_stable_root():
    a = ledger_for({"forecast": {"precip_next_3d_mm": 1}})
    b = ledger_for({"forecast": {"precip_next_3d_mm": 1}})
    assert a["root"] == b["root"]
    assert hash_pack({"x": 1}) != hash_pack({"x": 2})

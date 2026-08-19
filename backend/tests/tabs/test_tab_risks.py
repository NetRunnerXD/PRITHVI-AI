"""Risks tab: cards are scored at the pin, not a far state's bulletin."""

from app.ml.risk import all_risks
from app.services.locality import foreign_states_in
from .isolation import loc


def _feats(home):
    return {
        "lat": home.lat,
        "lon": home.lon,
        "precip_today_mm": 4.0,
        "precip_3d_mm": 12.0,
        "precip_7d_mm": 30.0,
        "soil_m3m3": 0.3,
        "temp_c": 29.0,
        "aqi": 80,
        "discharge_ratio": 1.0,
    }


def test_howrah_risk_labels_do_not_name_chhattisgarh():
    home = loc("Howrah")
    cards = all_risks(_feats(home), cap_hit=False, low_elev=True)
    blob = " ".join(f"{c.label} {c.id}" for c in cards)
    assert foreign_states_in(blob, home) == []
    assert "Chhattisgarh" not in blob
    assert cards
    assert all(0 <= c.score_pct <= 100 for c in cards)


def test_contradiction_raipur_risks_are_still_valid():
    home = loc("Raipur")
    cards = all_risks(_feats(home), cap_hit=False, low_elev=True)
    assert cards
    blob = " ".join(c.label for c in cards)
    assert "Howrah" not in blob

"""Overview / dashboard pin stays on the asked town."""

from app.services.location_svc import resolve_location
from .isolation import assert_home_pin, assert_no_foreign_state, loc


def test_overview_query_resolves_howrah_not_default():
    home = loc("Howrah")
    pin = resolve_location(q="Howrah")
    assert_home_pin(pin.model_dump(), home)
    assert pin.state == "West Bengal"
    assert "Chhattisgarh" not in pin.label


def test_contradiction_overview_raipur_is_not_howrah():
    howrah = loc("Howrah")
    raipur = loc("Raipur")
    assert howrah.state != raipur.state
    assert howrah.district != raipur.district
    assert abs(howrah.lon - raipur.lon) > 5
    assert_no_foreign_state(howrah.model_dump(), howrah)

"""Market tab: mandi query uses the pin's state+district, not a far state."""

from .isolation import loc


def test_howrah_mandi_key_is_west_bengal():
    home = loc("Howrah")
    assert home.state == "West Bengal"
    assert home.district == "Howrah"
    assert home.state != "Chhattisgarh"


def test_contradiction_raipur_mandi_key_is_not_howrah():
    home = loc("Raipur")
    assert home.state == "Chhattisgarh"
    assert home.district != "Howrah"

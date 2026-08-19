"""Nowcast tab: locked hours belong to the asked coordinates."""

from .isolation import loc


def test_howrah_and_raipur_nowcast_points_are_far():
    a = loc("Howrah")
    b = loc("Raipur")
    assert abs(a.lat - b.lat) > 3 or abs(a.lon - b.lon) > 3


def test_contradiction_malda_is_not_haldia():
    malda = loc("Malda")
    haldia = loc("Haldia")
    assert malda.district != haldia.district
    assert abs(malda.lat - haldia.lat) > 1.5

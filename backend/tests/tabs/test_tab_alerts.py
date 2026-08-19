"""Alerts tab: Sachet/CAP rows for Howrah must not be a Chhattisgarh bulletin."""

from app.services.locality import alert_belongs, port_relevant
from .isolation import loc


def test_sachet_chhattisgarh_item_dropped_for_howrah():
    home = loc("Howrah")
    foreign = {"title": "Orange warning for Chhattisgarh", "body": "Heavy rain over Raipur."}
    local = {"title": "Watch for Howrah and Hooghly", "body": "West Bengal districts."}
    generic = {"title": "Bay of Bengal watch", "body": "No state named."}
    assert not alert_belongs(foreign, home)
    assert alert_belongs(local, home)
    assert alert_belongs(generic, home)


def test_contradiction_raipur_keeps_chhattisgarh_alert():
    home = loc("Raipur")
    item = {"title": "Orange warning for Chhattisgarh", "body": "Raipur district."}
    assert alert_belongs(item, home)
    howrah_item = {"title": "Watch for Howrah", "body": "West Bengal"}
    assert not alert_belongs(howrah_item, home)


def test_hooghly_port_only_on_hooghly_belt():
    assert port_relevant(loc("Howrah"))
    assert port_relevant(loc("Haldia"))
    assert not port_relevant(loc("Jaipur"))
    assert not port_relevant(loc("Raipur"))
    assert not port_relevant(loc("Malda"))

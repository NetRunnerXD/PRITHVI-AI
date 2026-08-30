"""Map tab: nearby list is local, search does not jump to a far state."""

from app.services.location_svc import nearby, search
from .isolation import loc


def test_nearby_howrah_is_not_raipur():
    home = loc("Howrah")
    rows = nearby(home.lat, home.lon, limit=6)
    assert rows
    labels = " ".join(r.label for r in rows)
    assert "Raipur" not in labels
    assert "Chhattisgarh" not in labels
    for r in rows:
        assert abs(r.lat - home.lat) < 4
        assert abs(r.lon - home.lon) < 4


def test_weather_grid_is_world_bbox():
    from app.providers.weather_grid import EAST, NORTH, SOUTH, WEST, synthetic

    g = synthetic(0)
    assert g["south"] == SOUTH
    assert g["west"] == WEST
    assert g["north"] == NORTH
    assert g["east"] == EAST
    assert g["south"] < 0
    assert g["west"] < -100
    assert g["n"] > 100
    assert g.get("scope") == "world"


def test_map_pin_search_stays_india():
    from app.data.india_mask import in_india

    assert in_india(22.57, 88.36)
    assert not in_india(48.85, 2.35)


def test_contradiction_search_raipur_is_chhattisgarh():
    hits = search("Raipur")
    assert hits
    assert hits[0].state == "Chhattisgarh"
    assert hits[0].district != "Howrah"

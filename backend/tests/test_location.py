from app.services.location_svc import nearby, resolve_location, search


def test_search_pune():
    hits = search("Pune")
    assert hits
    assert hits[0].district == "Pune"
    assert hits[0].state == "Maharashtra"


def test_resolve_default_haldia():
    loc = resolve_location()
    assert loc.place_name == "Haldia"
    assert loc.district == "Purba Medinipur"
    assert loc.state == "West Bengal"


def test_nearby_excludes_self():
    loc = resolve_location(q="Kolkata")
    near = nearby(loc.lat, loc.lon, limit=5)
    assert len(near) == 5
    assert all(n.id != loc.id for n in near)


def test_resolve_haldia_is_west_bengal_town():
    loc = resolve_location(q="Haldia")
    assert loc.place_name == "Haldia"
    assert loc.state == "West Bengal"
    assert loc.place_kind == "city"


def test_resolve_cherrapunji_is_meghalaya():
    loc = resolve_location(q="Cherrapunji")
    assert loc.place_name == "Cherrapunji"
    assert loc.state == "Meghalaya"
    assert loc.district == "East Khasi Hills"


def test_resolve_puruliya_is_purulia_not_puri():
    loc = resolve_location(q="Puruliya")
    assert loc.district == "Purulia"
    assert loc.state == "West Bengal"
    assert loc.district != "Puri"
    from app.services.location_svc import resolve_named_place

    assert resolve_named_place("Puruliya").district == "Purulia"
    assert resolve_named_place("Puri").state == "Odisha"


def test_search_towns_shantiniketan():
    from app.data.india_towns import search_towns

    hits = search_towns("Shantiniketan")
    assert hits and hits[0]["name"] == "Santiniketan"

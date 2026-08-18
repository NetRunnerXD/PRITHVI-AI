"""Each successful fuzzy hit has a near-miss that must not resolve to the same place."""

from app.data.india_towns import search_towns
from app.services.location_svc import resolve_named_place


# query, forbidden place_name or district (case-insensitive)
FORBIDDEN = [
    ("Puruliya", "Puri"),
    ("Puri", "Purulia"),
    ("Pure", "Purulia"),
    ("Pure", "Puri"),
    ("Pur", "Purulia"),
    ("Pu", "Puri"),
    ("Calicut", "Kolkata"),
    ("Calicut", "Calcutta"),
    ("Calcutta", "Kozhikode"),
    ("Cherry", "Cherrapunji"),
    ("Bangor", "Bengaluru"),
    ("Bangor", "Bengaluru Urban"),
    ("Bombay", "Bengaluru"),
    ("Howrah", "Hogwarts"),
    ("Nadia", "Narnia"),
    ("Kochi", "Kolkata"),
    ("Pune", "Puri"),
    ("Pune", "Purulia"),
    ("Paris", "Patna"),
    ("Paris", "Puri"),
    ("Goa", "Goya"),
    ("Noida", "Nadia"),
]


def _names(loc) -> set[str]:
    if loc is None:
        return set()
    out = {loc.district.lower(), (loc.place_name or "").lower(), loc.label.lower()}
    return {x for x in out if x}


def test_near_misses_do_not_resolve_to_the_cousin():
    bad = []
    for q, forbidden in FORBIDDEN:
        loc = resolve_named_place(q)
        names = _names(loc)
        if forbidden.lower() in names or any(forbidden.lower() == n for n in names):
            bad.append((q, forbidden, loc.label if loc else None))
    assert not bad, bad


def test_puruliya_search_towns_does_not_return_puri():
    hits = search_towns("Puruliya", limit=5)
    assert all(t["name"] != "Puri" for t in hits)


def test_puri_still_resolves_to_puri_odisha():
    loc = resolve_named_place("Puri")
    assert loc is not None
    assert loc.district == "Puri" or loc.place_name == "Puri"
    assert loc.state == "Odisha"
    assert loc.district != "Purulia"


def test_pure_is_not_an_indian_place():
    assert resolve_named_place("Pure") is None
    assert resolve_named_place("Pur") is None
    assert resolve_named_place("Pu") is None


def test_cherra_alias_still_hits_but_cherry_does_not():
    """Contradiction of the Cherry≠Cherrapunji miss: the real alias must still work."""
    assert resolve_named_place("Cherry") is None
    loc = resolve_named_place("Cherra")
    assert loc is not None
    assert loc.place_name == "Cherrapunji"


def test_calicut_is_not_calcutta():
    loc = resolve_named_place("Calicut")
    assert loc is not None
    assert loc.state == "Kerala"
    assert "kolkata" not in _names(loc)
    cal = resolve_named_place("Calcutta")
    assert cal is not None
    assert cal.state == "West Bengal"
    assert cal.district == "Kolkata"

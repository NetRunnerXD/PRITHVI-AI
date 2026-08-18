"""Gazetteer hits for real Indian names, including census spellings."""

from app.agents.dimensions import mentioned_place
from app.data.india_districts import extract_place, search_districts
from app.data.india_towns import extract_town, search_towns
from app.services.location_svc import resolve_named_place, resolve_location


HITS = [
    ("Puruliya", "Purulia", "West Bengal"),
    ("Purulia", "Purulia", "West Bengal"),
    ("Puri", "Puri", "Odisha"),
    ("Calcutta", "Kolkata", "West Bengal"),
    ("Calicut", "Kozhikode", "Kerala"),
    ("Bombay", "Mumbai", "Maharashtra"),
    ("Madras", "Chennai", "Tamil Nadu"),
    ("Bangalore", "Bengaluru Urban", "Karnataka"),
    ("Trivandrum", "Thiruvananthapuram", "Kerala"),
    ("Pondicherry", "Puducherry", "Puducherry"),
    ("Gurgaon", "Gurugram", "Haryana"),
    ("Allahabad", "Prayagraj", "Uttar Pradesh"),
    ("Vizag", "Visakhapatnam", "Andhra Pradesh"),
    ("Cherrapunjee", "Cherrapunji", "Meghalaya"),
    ("Shantiniketan", "Santiniketan", "West Bengal"),
    ("Cochin", "Kochi", "Kerala"),
    ("Benares", "Varanasi", "Uttar Pradesh"),
    ("Noida", "Noida", "Uttar Pradesh"),
]


def test_resolve_named_hits():
    bad = []
    for q, expect_name, expect_state in HITS:
        loc = resolve_named_place(q)
        if loc is None:
            bad.append((q, None, expect_name))
            continue
        got = loc.place_name or loc.district
        if expect_name.lower() not in {got.lower(), loc.district.lower()} or loc.state != expect_state:
            bad.append((q, (got, loc.district, loc.state), (expect_name, expect_state)))
    assert not bad, bad


def test_puruliya_extract_and_search():
    assert extract_place("weather in Puruliya") == "Purulia"
    assert mentioned_place("Puruliya") == "Purulia"
    hits = search_districts("Puruliya", limit=3)
    assert hits and hits[0]["district"] == "Purulia"
    assert hits[0]["state"] == "West Bengal"


def test_cherrapunjee_is_the_town():
    assert extract_town("Cherrapunjee") == "Cherrapunji"
    loc = resolve_named_place("Cherrapunjee")
    assert loc and loc.place_name == "Cherrapunji"
    assert loc.state == "Meghalaya"


def test_resolve_location_still_defaults_when_q_missing():
    loc = resolve_location()
    assert loc.place_name == "Haldia"
    named = resolve_named_place("not-a-real-place-xyz")
    assert named is None


def test_search_towns_shantiniketan_still_works():
    hits = search_towns("Shantiniketan")
    assert hits and hits[0]["name"] == "Santiniketan"


def test_contradiction_punctuation_and_district_suffix():
    """If Puruliya hits, so must 'Puruliya district' and 'Puruliya?' — not a different district."""
    for q in ("Puruliya district", "Puruliya?", "PURULIYA", "purulia,"):
        loc = resolve_named_place(q)
        assert loc is not None, q
        assert loc.district == "Purulia", q
        assert loc.state == "West Bengal", q

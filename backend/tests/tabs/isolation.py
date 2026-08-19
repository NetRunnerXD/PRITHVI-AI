"""Shared isolation checks. Each tab test uses these, then adds a contradiction."""

from __future__ import annotations

from app.data.india_districts import all_states
from app.schemas.location import Location
from app.services.locality import foreign_states_in
from app.services.location_svc import resolve_named_place

PAIRS = [
    ("Howrah", "Chhattisgarh"),
    ("Malda", "Rajasthan"),
    ("Puri", "Punjab"),
    ("Jaipur", "Kerala"),
]


def loc(name: str) -> Location:
    hit = resolve_named_place(name)
    assert hit is not None, name
    return hit


def blob_of(obj) -> str:
    return str(obj).lower()


def assert_home_pin(payload: dict, home: Location) -> None:
    where = payload.get("location") or payload
    assert where.get("state") == home.state, (where, home.state)
    district = where.get("district") or ""
    place = where.get("place_name") or ""
    assert home.district in {district, place} or home.place_name in {place, district} or (
        home.state == where.get("state") and home.district.lower() in (district + place).lower()
    )


def assert_no_foreign_state(payload, home: Location, extra_ok: tuple[str, ...] = ()) -> None:
    blob = blob_of(payload)
    leaked = [s for s in foreign_states_in(blob, home) if s not in extra_ok]
    # National sources may mention "India"; never a far inland state in a local bulletin.
    assert not leaked, leaked


def far_of(name: str) -> str:
    for a, b in PAIRS:
        if a.lower() == name.lower():
            return b
    home = loc(name)
    for s in all_states():
        if s != home.state:
            return s
    return "Chhattisgarh"

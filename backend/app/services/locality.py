"""Keep a place's bulletin on that place. Howrah must not inherit Chhattisgarh."""

from __future__ import annotations

from app.data.india_districts import all_states
from app.data.physiography import HOOGHLY_DISTRICTS, HOOGHLY_TOWNS, hugli_relevant
from app.schemas.location import Location


def _needles(loc: Location) -> list[str]:
    bits = [loc.state, loc.district, loc.place_name or ""]
    return [b.lower() for b in bits if b and len(b) >= 4]


def foreign_states_in(text: str, home: Location) -> list[str]:
    """Other Indian states named in a blob (not the home state)."""
    blob = (text or "").lower()
    home_s = (home.state or "").lower()
    found: list[str] = []
    for s in all_states():
        sl = s.lower()
        if sl == home_s or len(sl) < 5:
            continue
        if sl in blob:
            found.append(s)
    return found


def alert_belongs(item: dict, loc: Location) -> bool:
    """Keep a CAP/Sachet row if it names this place or names no other state."""
    blob = f"{item.get('title') or ''} {item.get('body') or ''}"
    low = blob.lower()
    if any(n in low for n in _needles(loc)):
        return True
    return not foreign_states_in(blob, loc)


def port_relevant(loc: Location) -> bool:
    return hugli_relevant(loc=loc)


def nearby_is_local(home: Location, other: Location, max_deg: float = 4.0) -> bool:
    return abs(home.lat - other.lat) <= max_deg and abs(home.lon - other.lon) <= max_deg

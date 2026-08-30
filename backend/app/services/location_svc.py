from __future__ import annotations

from app.config import get_settings
from app.data.blocked_places import is_blocked_name
from app.data.india_capitals import capital_of
from app.data.india_districts import (
    all_districts,
    all_states,
    default_district,
    districts_in_state,
    nearest,
    search_districts,
)
from app.data.india_towns import search_towns
from app.schemas.location import Location


def compose_label(name: str | None, state: str | None) -> str:
    """Never emit 'Delhi, Delhi'."""
    n = (name or "").strip()
    s = (state or "").strip()
    if not s:
        return n
    if not n:
        return s
    nl, sl = n.lower(), s.lower()
    if nl == sl or nl in sl or sl in nl:
        return n
    return f"{n}, {s}"


def _from_row(row: dict, **over) -> Location:
    data = {
        "id": row["id"],
        "label": row["label"],
        "country": "IN",
        "state": row["state"],
        "district": row["district"],
        "imd_subdivision": row.get("imd_subdivision"),
        "lat": row["lat"],
        "lon": row["lon"],
        "timezone": "Asia/Kolkata",
        "crop_hint": row.get("crop_hint") or "aman_rice",
        "place_kind": row.get("place_kind") or "district",
        "place_name": row.get("place_name") or row.get("district"),
    }
    data.update({k: v for k, v in over.items() if v is not None})
    return Location(**data)


def _kind_from_feature(code: str | None) -> str:
    c = (code or "").upper()
    if c in {"PPLC", "PPLA", "PPLA2", "PPLA3"}:
        return "city"
    if c in {"PPL", "PPLX", "PPLL"}:
        return "town"
    if c.startswith("ADM"):
        return "district"
    return "place"


def _capital_loc(row: dict) -> Location:
    name = row["name"]
    state = row["state"]
    return Location(
        id=f"capital:{name.lower().replace(' ', '_')}_{state[:3].lower()}",
        label=compose_label(name, state),
        state=state,
        district=row["district"],
        lat=float(row["lat"]),
        lon=float(row["lon"]),
        place_kind=row.get("kind") or "city",
        place_name=name,
    )


def location_from_geocode(raw: dict, query: str | None = None) -> Location:
    name = str(raw.get("name") or query or "").strip()
    admin1 = str(raw.get("admin1") or "").strip()
    admin2 = str(raw.get("admin2") or admin1 or name).strip()
    return Location(
        id=f"om:{raw.get('id') or name.lower().replace(' ', '_')}",
        label=compose_label(name, admin1),
        state=admin1 or "India",
        district=admin2 or name,
        lat=float(raw["latitude"]),
        lon=float(raw["longitude"]),
        place_kind=_kind_from_feature(raw.get("feature_code")),
        place_name=name,
    )


def resolve_named_place(q: str | None) -> Location | None:
    """Gazetteer town / district / state capital. None if not a local hit (no Haldia fallback)."""
    from app.data.closed_class import is_closed_query
    from app.data.fuzzy import clean_place_query, match_rank, ratio
    from app.data.india_districts import extract_place, search_districts
    from app.data.india_towns import extract_town, search_towns

    needle = clean_place_query(q or "")
    if not needle or is_closed_query(needle) or is_closed_query(q):
        return None

    from app.data.india_districts import is_state_name

    # City-states and bare state names are a forecast at the HQ, not a miss.
    if is_state_name(needle):
        cap = capital_of(needle)
        if cap:
            return _capital_loc(cap)

    scored: list[tuple[float, int, str, object]] = []

    def _accept(kind: str, name: str, aliases: list[str], payload: object) -> None:
        ranks = [match_rank(needle, n) for n in [name, *aliases] if n]
        ranks = [r for r in ranks if r is not None]
        if not ranks:
            return
        scored.append((float(min(ranks)), 0 if kind == "town" else 1, name, payload))

    for t in search_towns(needle, limit=8):
        _accept("town", t["name"], list(t.get("aliases") or []), t)
    for d in search_districts(needle, limit=8):
        _accept("dist", d["district"], list(d.get("aliases") or []), d)

    if scored:
        scored.sort(key=lambda x: (x[0], x[1], -ratio(needle, x[2]), x[2]))
        best = scored[0]
        if best[0] <= 1:
            if best[1] == 0:
                return _town_loc(best[3])  # type: ignore[arg-type]
            loc = _from_row(best[3])  # type: ignore[arg-type]
            return loc.model_copy(update={"label": compose_label(loc.place_name or loc.district, loc.state)})

    cap = capital_of(needle)
    if cap:
        return _capital_loc(cap)

    town = extract_town(needle)
    if town:
        found = search_towns(town, limit=1)
        if found:
            return _town_loc(found[0])
    dist = extract_place(needle)
    if dist:
        found = search_districts(dist, limit=1)
        if found:
            loc = _from_row(found[0])
            return loc.model_copy(update={"label": compose_label(loc.place_name or loc.district, loc.state)})
    return None


async def resolve_india_place(q: str | None) -> Location | None:
    """Gazetteer, then Open-Meteo India geocode. Covers any real Indian town/district."""
    from app.data.closed_class import is_closed_query

    needle = (q or "").strip()
    if not needle:
        return None
    if is_blocked_name(needle) or is_closed_query(needle):
        return None
    local = resolve_named_place(needle)
    if local:
        return local
    try:
        from app.providers import open_meteo

        raw = await open_meteo.geocode_india(needle)
    except Exception:
        raw = []
    if not raw:
        return None
    # Prefer an exact / fold-close name over a distant cousin OM ranked first.
    from app.data.fuzzy import fold, match_rank

    def _score(row: dict) -> tuple:
        name = str(row.get("name") or "")
        rank = match_rank(needle, name)
        exact = 0 if fold(needle) == fold(name) else 1
        rkey = 0 if rank == 0 else 1 if rank == 1 else 9
        return (exact, rkey, name.lower())

    ranked = sorted(raw, key=_score)
    best = ranked[0]
    name = str(best.get("name") or "")
    rank = match_rank(needle, name)
    if rank not in {0, 1}:
        return None
    return location_from_geocode(best, needle)


def resolve_location(loc: Location | None = None, q: str | None = None,
                     lat: float | None = None, lon: float | None = None) -> Location:
    if loc is not None:
        return loc
    if q:
        named = resolve_named_place(q)
        if named:
            if lat is not None and lon is not None:
                return named.model_copy(update={"lat": lat, "lon": lon})
            return named
    if lat is not None and lon is not None:
        return _from_row(nearest(lat, lon), lat=lat, lon=lon)
    s = get_settings()
    place = (s.default_place or "").strip()
    if place:
        towns = search_towns(place, limit=1)
        if towns:
            return _town_loc(towns[0])
    row = default_district()
    return _from_row(row, lat=s.default_lat, lon=s.default_lon)


def search(q: str, limit: int = 8) -> list[Location]:
    return [_from_row(r) for r in search_districts(q, limit=limit)]


def _town_loc(t: dict) -> Location:
    return Location(
        id=f"town:{t['name'].lower().replace(' ', '_')}_{t['state'][:3].lower()}",
        label=compose_label(t["name"], t["state"]),
        state=t["state"],
        district=t["district"],
        lat=t["lat"],
        lon=t["lon"],
        place_kind=t.get("kind") or "town",
        place_name=t["name"],
    )


async def search_places(q: str, limit: int = 8) -> list[Location]:
    """Districts + curated towns + Open-Meteo India cities."""
    qlow = (q or "").strip().lower()
    towns = [_town_loc(t) for t in search_towns(q, limit=limit)]
    local = search(q, limit=limit)
    extra: list[Location] = []
    try:
        from app.providers import open_meteo

        raw = await open_meteo.geocode_india(q)
    except Exception:
        raw = []
    seen = {(round(x.lat, 2), round(x.lon, 2)) for x in towns + local}
    seen_names = {((x.place_name or x.district).lower(), x.state.lower()) for x in towns}
    for r in raw:
        lat, lon = r.get("latitude"), r.get("longitude")
        if lat is None or lon is None:
            continue
        name = str(r.get("name") or q).strip()
        admin1 = str(r.get("admin1") or "").strip()
        admin2 = str(r.get("admin2") or admin1 or name).strip()
        key = (round(float(lat), 2), round(float(lon), 2))
        if key in seen or (name.lower(), admin1.lower()) in seen_names:
            continue
        seen.add(key)
        extra.append(location_from_geocode(r, q))
    merged = towns + local + extra
    merged.sort(
        key=lambda loc: (
            0 if str(loc.id).startswith("town:") else 1,
            0 if (loc.place_name or "").lower() == qlow else 1,
            0 if loc.place_kind in {"city", "town"} and qlow and qlow in (loc.place_name or "").lower() else 1,
            0 if loc.place_kind == "district" and loc.district.lower() == qlow else 1,
            loc.label,
        )
    )
    # unique by label
    out: list[Location] = []
    used = set()
    for loc in merged:
        if loc.label in used:
            continue
        used.add(loc.label)
        out.append(loc)
        if len(out) >= limit:
            break
    return out


def list_states() -> list[str]:
    return all_states()


def list_districts(state: str | None = None) -> list[Location]:
    rows = districts_in_state(state) if state else all_districts()
    return [_from_row(r) for r in rows]


def nearby(lat: float, lon: float, limit: int = 8) -> list[Location]:
    """Towns first (Haldia mesh), then district HQs. Excludes the query point."""
    from app.data.india_towns import TOWNS

    scored: list[tuple[float, Location]] = []
    for t in TOWNS:
        d2 = (float(t["lat"]) - lat) ** 2 + (float(t["lon"]) - lon) ** 2
        if d2 < 1e-8:
            continue
        scored.append((d2, _town_loc(t)))
    scored.sort(key=lambda x: x[0])
    out: list[Location] = []
    seen: set[str] = set()
    for _, loc in scored:
        if loc.id in seen:
            continue
        seen.add(loc.id)
        out.append(loc)
        if len(out) >= limit:
            return out
    ranked = sorted(
        all_districts(),
        key=lambda d: (d["lat"] - lat) ** 2 + (d["lon"] - lon) ** 2,
    )
    for row in ranked:
        loc = _from_row(row)
        if loc.id in seen or (abs(loc.lat - lat) < 1e-4 and abs(loc.lon - lon) < 1e-4):
            continue
        out.append(loc)
        if len(out) >= limit:
            break
    return out

from fastapi import Query

from app.schemas.location import Location
from app.services.location_svc import resolve_location


def loc_from_query(
    district: str | None = Query(default=None),
    place: str | None = Query(default=None),
    lat: float | None = Query(default=None),
    lon: float | None = Query(default=None),
) -> Location:
    loc = resolve_location(q=place or district, lat=lat, lon=lon)
    if lat is not None and lon is not None:
        update: dict = {"lat": lat, "lon": lon}
        if place:
            update["place_name"] = place
            update["place_kind"] = loc.place_kind if loc.place_kind != "district" else "place"
            if loc.state:
                update["label"] = f"{place}, {loc.state}"
            else:
                update["label"] = place
        loc = loc.model_copy(update=update)
    return loc

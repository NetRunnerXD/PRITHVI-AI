"""GDACS multi-hazard events (EQ, flood, cyclone, tsunami) for the India box."""

from __future__ import annotations

from typing import Any

from app import cache
from app.data.india_mask import in_india
from app.providers.http import client

_FOREIGN = (
    "philippines", "indonesia", "myanmar", "vietnam", "malaysia", "thailand",
    "china", "japan", "somalia", "madagascar", "mozambique", "oman", "yemen",
    "bangladesh", "nepal", "bhutan", "sri lanka", "pakistan", "afghanistan",
)

RSS = "https://www.gdacs.org/xml/rss.xml"
SEARCH = "https://www.gdacs.org/gdacsapi/api/events/geteventlist/SEARCH"


def _in_box(lat: float | None, lon: float | None) -> bool:
    """Coarse India bbox only — not SE Asia. Fine filter is in_india / India mention."""
    if lat is None or lon is None:
        return False
    return 6.4 <= float(lat) <= 37.5 and 66.0 <= float(lon) <= 98.0


def _mentions_india(row: dict[str, Any]) -> bool:
    blob = " ".join(
        str(row.get(k) or "")
        for k in ("country", "name", "description", "iso3", "eventname")
    ).lower()
    ac = row.get("affectedcountries")
    if isinstance(ac, list):
        blob += " " + " ".join(str(x).lower() for x in ac)
    elif ac:
        blob += " " + str(ac).lower()
    return "india" in blob or "ind " in blob or blob.endswith("ind")


def parse_events(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out = []
    for row in rows:
        et = str(row.get("eventtype") or row.get("eventType") or row.get("type") or "").upper()
        lat = row.get("latitude") or row.get("lat")
        lon = row.get("longitude") or row.get("lon")
        try:
            lat_f = float(lat) if lat is not None else None
            lon_f = float(lon) if lon is not None else None
        except (TypeError, ValueError):
            lat_f = lon_f = None
        india = _mentions_india(row)
        on_land = lat_f is not None and lon_f is not None and in_india(lat_f, lon_f)
        in_seas = lat_f is not None and lon_f is not None and _in_box(lat_f, lon_f)
        blob = " ".join(
            str(row.get(k) or "")
            for k in ("country", "name", "description", "iso3", "eventname")
        ).lower()
        foreign = any(f in blob for f in _FOREIGN)
        if foreign and not india:
            continue
        if not india and not on_land:
            if not (et in {"TC", "TS"} and in_seas):
                continue
        name = row.get("name") or row.get("eventname") or row.get("country") or et
        eid = str(row.get("eventid") or row.get("eventId") or name)[:64]
        url = None
        if row.get("url"):
            url = str(row.get("url"))
        elif eid:
            url = f"https://www.gdacs.org/report.aspx?eventid={eid}"
        out.append(
            {
                "id": eid,
                "title": f"GDACS {et} · {name}"[:160],
                "body": str(row.get("description") or row.get("alertlevel") or "")[:400],
                "event_type": et,
                "alert_level": row.get("alertlevel") or row.get("alertLevel"),
                "lat": lat_f,
                "lon": lon_f,
                "url": url,
                "source": "GDACS",
            }
        )
    return out[:12]


async def events() -> tuple[list[dict[str, Any]], str]:
    hit = cache.get("gdacs:in")
    if hit is not None:
        return hit, "ok" if hit else "empty"

    async def factory_json() -> list[dict[str, Any]]:
        r = await client().get(
            SEARCH,
            params={"eventlist": "EQ,TC,FL,TS"},
            timeout=12.0,
        )
        if r.status_code >= 400:
            return []
        data = r.json()
        features = data if isinstance(data, list) else (data.get("features") or data.get("events") or [])
        rows = []
        for f in features:
            if isinstance(f, dict) and "properties" in f:
                props = dict(f.get("properties") or {})
                coords = ((f.get("geometry") or {}).get("coordinates")) or [None, None]
                props.setdefault("lon", coords[0] if coords else None)
                props.setdefault("lat", coords[1] if len(coords) > 1 else None)
                rows.append(props)
            elif isinstance(f, dict):
                rows.append(f)
        return parse_events(rows)

    try:
        items = await factory_json()
    except Exception:
        items = []
    cache.set("gdacs:in", items, 15 * 60)
    return items, "ok" if items else "empty"

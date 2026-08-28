"""data.gov.in OGD client — CPCB NAQI + Agmarknet mandi prices."""

from __future__ import annotations

from typing import Any

from app import cache
from app.config import get_settings
from app.providers.http import client

BASE = "https://api.data.gov.in/resource"
AQI_ID = "3b01bcb8-0b14-4abf-b6f2-c1bfd384ba69"
MANDI_ID = "9ef84268-d588-465a-a308-a864a43d0070"

STATE_ALIASES = {
    "delhi": ["Delhi", "NCT of Delhi"],
    "jammu and kashmir": ["Jammu and Kashmir", "Jammu & Kashmir"],
    "andaman and nicobar": ["Andaman and Nicobar", "Andaman & Nicobar Islands"],
    "dadra and nagar haveli and daman and diu": ["Dadra and Nagar Haveli", "Daman and Diu"],
    "puducherry": ["Puducherry", "Pondicherry"],
}

CITY_ALIASES = {
    "haldia": ["Haldia"],
    "siliguri": ["Siliguri"],
    "darjeeling": ["Darjeeling"],
    "asansol": ["Asansol"],
    "durgapur": ["Durgapur"],
    "purba medinipur": ["Haldia"],
    "paschim bardhaman": ["Asansol", "Durgapur"],
    "new delhi": ["Delhi"],
    "bengaluru urban": ["Bengaluru", "Bangalore"],
    "mumbai": ["Mumbai"],
    "chennai": ["Chennai"],
    "hyderabad": ["Hyderabad"],
    "kolkata": ["Kolkata"],
    "howrah": ["Howrah", "Kolkata"],
    "hooghly": ["Howrah", "Kolkata"],
    "north 24 parganas": ["Barrackpore", "Kolkata"],
    "south 24 parganas": ["Kolkata"],
    "nadia": ["Barrackpore", "Kalyani", "Kolkata"],
    "gurugram": ["Gurugram", "Gurgaon"],
    "pune": ["Pune"],
    "ahmedabad": ["Ahmedabad"],
    "jaipur": ["Jaipur"],
    "lucknow": ["Lucknow"],
    "patna": ["Patna"],
    "bhopal": ["Bhopal"],
    "chandigarh": ["Chandigarh"],
}

AQI_CATEGORY = (
    (50, "Good"),
    (100, "Satisfactory"),
    (200, "Moderate"),
    (300, "Poor"),
    (400, "Very Poor"),
    (500, "Severe"),
)


def _key() -> str | None:
    return get_settings().data_gov_in_api_key


def aqi_category(value: float) -> str:
    for cap, label in AQI_CATEGORY:
        if value <= cap:
            return label
    return "Severe"


async def resource(
    resource_id: str,
    limit: int = 20,
    filters: dict[str, str] | None = None,
    offset: int = 0,
) -> tuple[dict[str, Any] | None, str]:
    if not _key():
        return None, "missing_key"
    params: dict[str, Any] = {
        "api-key": _key(),
        "format": "json",
        "limit": limit,
        "offset": offset,
    }
    if filters:
        for k, v in filters.items():
            params[f"filters[{k}]"] = v
    try:
        r = await client().get(f"{BASE}/{resource_id}", params=params)
        if r.status_code in {401, 403}:
            return None, "unauthorized"
        r.raise_for_status()
        data = r.json()
        if str(data.get("status", "ok")).lower() not in {"ok", "success"} and not data.get("records"):
            return data, "error"
        return data, "ok"
    except Exception:
        return None, "error"


def _num(v: Any) -> float | None:
    if v is None or v == "" or str(v).upper() in {"NA", "N/A", "-"}:
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _states(state: str) -> list[str]:
    return STATE_ALIASES.get(state.lower(), [state])


async def _aqi_records(state: str) -> list[dict[str, Any]]:
    recs: list[dict[str, Any]] = []
    for st in _states(state):
        payload, status = await resource(AQI_ID, limit=500, filters={"state": st})
        if status == "ok" and payload:
            recs.extend(payload.get("records") or [])
        if recs:
            break
    return recs


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    from math import atan2, cos, radians, sin, sqrt

    r = 6371.0
    p1, p2 = radians(lat1), radians(lat2)
    dp = radians(lat2 - lat1)
    dl = radians(lon2 - lon1)
    a = sin(dp / 2) ** 2 + cos(p1) * cos(p2) * sin(dl / 2) ** 2
    return 2 * r * atan2(sqrt(a), sqrt(max(0.0, 1 - a)))


def _group_stations(records: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    by: dict[str, list[dict[str, Any]]] = {}
    for rec in records:
        name = rec.get("station") or rec.get("city") or ""
        by.setdefault(name, []).append(rec)
    return by


def _nearest_station(
    records: list[dict[str, Any]], lat: float, lon: float, place: str = ""
) -> tuple[str, list[dict[str, Any]], str]:
    by_station = _group_stations(records)
    q = (place or "").strip().lower()
    aliases = CITY_ALIASES.get(q, [place] if place else [])
    keys = {q, *[a.lower() for a in aliases if a]}
    if q:
        for name, rows in by_station.items():
            city = (rows[0].get("city") or "").lower()
            st = name.lower()
            if any(k and (k in city or k in st or city == k) for k in keys):
                return name, rows, "city"
    best_name = ""
    best_d = 1e18
    for rec in records:
        name = rec.get("station") or rec.get("city") or ""
        slat, slon = _num(rec.get("latitude")), _num(rec.get("longitude"))
        if slat is None or slon is None:
            continue
        d = (slat - lat) ** 2 + (slon - lon) ** 2
        if d < best_d:
            best_d = d
            best_name = name
    return best_name, by_station.get(best_name) or [], "nearest"


async def nearest_aqi(
    lat: float, lon: float, state: str, district: str = "", place: str = ""
) -> tuple[dict[str, Any] | None, str]:
    if not _key():
        return None, "missing_key"
    cache_key = f"ogd:aqi:{round(lat, 2)}:{round(lon, 2)}:{(place or district or '').lower()}"
    hit = cache.get(cache_key)
    if hit is not None:
        return hit, "ok"
    recs = await _aqi_records(state)
    if not recs:
        return None, "empty"
    query = place or district
    station, rows, match = _nearest_station(recs, lat, lon, query)
    pollutants: dict[str, float] = {}
    sample = rows[0] if rows else {}
    for rec in rows:
        pid = (rec.get("pollutant_id") or "").upper().replace(".", "")
        avg = _num(rec.get("avg_value") or rec.get("pollutant_avg"))
        if not pid or avg is None:
            continue
        pollutants[pid] = avg
    if not pollutants:
        return None, "empty"
    value = max(pollutants.values())
    dominant = max(pollutants, key=pollutants.get)
    slat, slon = _num(sample.get("latitude")), _num(sample.get("longitude"))
    dist_km = None
    if slat is not None and slon is not None:
        dist_km = round(_haversine_km(lat, lon, slat, slon), 1)
    city = sample.get("city") or ""
    queried = query or district
    in_place = bool(queried) and queried.lower() in (city.lower() + " " + (station or "").lower())
    out = {
        "value": int(round(value)),
        "category": aqi_category(value),
        "dominant_pollutant": dominant,
        "pollutants": pollutants,
        "station": station,
        "city": city,
        "state": sample.get("state"),
        "updated": sample.get("last_update"),
        "lat": slat,
        "lon": slon,
        "source": "data.gov.in / CPCB",
        "resource_id": AQI_ID,
        "district_query": district,
        "queried_place": queried,
        "match": match,
        "distance_km": dist_km,
        "is_local_station": in_place or match == "city",
        "note": (
            f"CPCB station is in {city}"
            + (f", {dist_km} km from {queried}" if dist_km is not None and queried else "")
            + ("" if in_place or match == "city" else f" — not a {queried} city monitor")
        ),
    }
    cache.set(cache_key, out, 20 * 60)
    return out, "ok"


async def mandi_prices(state: str, district: str, limit: int = 40) -> tuple[list[dict[str, Any]], str]:
    if not _key():
        return [], "missing_key"
    cache_key = f"ogd:mandi:{state}:{district}"
    hit = cache.get(cache_key)
    if hit is not None:
        return hit, "ok"
    payload, status = await resource(
        MANDI_ID,
        limit=limit,
        filters={"state": state, "district": district},
    )
    if status != "ok" or not payload:
        return [], status
    rows = []
    for rec in payload.get("records") or []:
        modal = _num(rec.get("modal_price"))
        if modal is None:
            continue
        rows.append(
            {
                "commodity": rec.get("commodity"),
                "variety": rec.get("variety"),
                "market": rec.get("market"),
                "grade": rec.get("grade"),
                "date": rec.get("arrival_date"),
                "min_price": _num(rec.get("min_price")),
                "max_price": _num(rec.get("max_price")),
                "modal_price": modal,
                "unit": "INR/quintal",
            }
        )
    rows.sort(key=lambda r: r["modal_price"], reverse=True)
    cache.set(cache_key, rows, 30 * 60)
    return rows, "ok" if rows else "empty"


async def mandi_by_state(state: str, limit: int = 120) -> tuple[dict[str, list[dict[str, Any]]], str]:
    if not _key():
        return {}, "missing_key"
    cache_key = f"ogd:mandi-state:{state}"
    hit = cache.get(cache_key)
    if hit is not None:
        return hit, "ok"
    payload, status = await resource(MANDI_ID, limit=limit, filters={"state": state})
    if status != "ok" or not payload:
        return {}, status
    grouped: dict[str, list[dict[str, Any]]] = {}
    for rec in payload.get("records") or []:
        modal = _num(rec.get("modal_price"))
        if modal is None:
            continue
        dist = rec.get("district") or "Unknown"
        grouped.setdefault(dist, []).append(
            {
                "commodity": rec.get("commodity"),
                "market": rec.get("market"),
                "modal_price": modal,
                "date": rec.get("arrival_date"),
                "unit": "INR/quintal",
            }
        )
    cache.set(cache_key, grouped, 30 * 60)
    return grouped, "ok" if grouped else "empty"

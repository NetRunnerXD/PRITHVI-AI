"""India physiography for nowcast overlays.

Locked millimetres stay on Open-Meteo at the pin. These boxes only change
local chips: Hugli tide, CWC label, ponding scale, Kal Baisakhi vs storm.
"""

from __future__ import annotations

from typing import Any

HOOGHLY_DISTRICTS = {
    "Howrah",
    "Hooghly",
    "Kolkata",
    "Purba Medinipur",
    "North 24 Parganas",
    "South 24 Parganas",
}
HOOGHLY_TOWNS = {
    "Haldia",
    "Howrah",
    "Kolkata",
    "Digha",
    "Tamluk",
    "Diamond Harbour",
    "Sagar",
    "Sagar Island",
    "Kakdwip",
    "Gangra",
}

OROGRAPHIC_STATES = {
    "Himachal Pradesh",
    "Uttarakhand",
    "Sikkim",
    "Arunachal Pradesh",
    "Meghalaya",
    "Nagaland",
    "Manipur",
    "Mizoram",
    "Tripura",
    "Jammu and Kashmir",
    "Ladakh",
}
OROGRAPHIC_DISTRICTS = {
    "Darjeeling",
    "Kalimpong",
    "Idukki",
    "Wayanad",
    "Palakkad",
    "Kodagu",
    "Udupi",
    "Uttara Kannada",
    "Dakshina Kannada",
    "Ratnagiri",
    "Sindhudurg",
    "The Nilgiris",
    "Nilgiris",
}

ARID_DISTRICTS = {
    "Jaisalmer",
    "Barmer",
    "Bikaner",
    "Jodhpur",
    "Jalore",
    "Ganganagar",
    "Hanumangarh",
    "Churu",
    "Nagaur",
    "Pali",
    "Kachchh",
    "Kutch",
    "Banaskantha",
    "Patan",
    "Leh",
    "Kargil",
    "Anantapur",
    "Anantapuramu",
}

KAL_STATES = {
    "West Bengal",
    "Jharkhand",
    "Bihar",
    "Odisha",
    "Assam",
    "Tripura",
}

# Specific first. kind, lat0, lat1, lon0, lon1
_BOXES: list[tuple[str, float, float, float, float]] = [
    ("hugli", 21.55, 22.75, 87.65, 88.55),
    ("arid", 24.6, 30.2, 69.4, 75.2),
    ("arid", 22.6, 24.9, 68.4, 71.8),
    ("arid", 32.5, 35.6, 76.4, 79.6),
    ("orographic", 30.4, 35.6, 74.4, 80.6),
    ("orographic", 28.8, 31.6, 77.8, 81.2),
    ("orographic", 26.0, 29.6, 87.6, 97.4),
    ("orographic", 24.8, 26.3, 89.7, 93.0),
    ("orographic", 8.1, 16.6, 73.0, 76.4),
    ("orographic", 16.5, 21.0, 72.7, 73.55),
    ("delta", 21.4, 24.1, 87.4, 89.8),
    ("delta", 19.7, 21.6, 85.4, 87.1),
    ("delta", 15.5, 17.3, 80.4, 82.6),
    ("island", 6.5, 14.0, 92.0, 94.2),
    ("plains", 24.8, 30.4, 75.0, 88.5),
]

_POND_SCALE = {
    "hugli": 1.0,
    "delta": 1.0,
    "plains": 0.85,
    "coast": 0.75,
    "plateau": 0.65,
    "island": 0.55,
    "orographic": 0.35,
    "arid": 0.18,
}

_LABEL = {
    "hugli": "Hugli estuary",
    "delta": "coastal delta",
    "plains": "alluvial plain",
    "coast": "open coast",
    "plateau": "peninsula / plateau",
    "island": "island",
    "orographic": "hills / mountains",
    "arid": "arid / rain-shadow",
}


def hugli_relevant(
    lat: float | None = None,
    lon: float | None = None,
    *,
    state: str | None = None,
    district: str | None = None,
    place: str | None = None,
    loc: Any = None,
) -> bool:
    if loc is not None:
        state = getattr(loc, "state", None) or state
        district = getattr(loc, "district", None) or district
        place = getattr(loc, "place_name", None) or place
        if getattr(loc, "lat", None) is not None:
            lat = loc.lat
        if getattr(loc, "lon", None) is not None:
            lon = loc.lon
    if (state or "") == "West Bengal" and (
        (district or "") in HOOGHLY_DISTRICTS or (place or "") in HOOGHLY_TOWNS
    ):
        return True
    if lat is None or lon is None:
        return False
    return 21.55 <= float(lat) <= 22.75 and 87.65 <= float(lon) <= 88.55


def _kind_from_admin(state: str | None, district: str | None, place: str | None) -> str | None:
    if (state or "") in OROGRAPHIC_STATES or (district or "") in OROGRAPHIC_DISTRICTS:
        return "orographic"
    if (state or "") in {"Kerala", "Goa"}:
        return "orographic"
    if (district or "") in ARID_DISTRICTS or (place or "") in ARID_DISTRICTS:
        return "arid"
    return None


def _kind_from_box(lat: float, lon: float) -> str | None:
    for kind, la, lb, oa, ob in _BOXES:
        if la <= lat <= lb and oa <= lon <= ob:
            return kind
    return None


def _kal_belt(kind: str, state: str | None, lat: float | None, lon: float | None) -> bool:
    if (state or "") in KAL_STATES:
        return True
    if kind in {"hugli", "delta"}:
        return True
    if lat is None or lon is None:
        return False
    return 20.4 <= float(lat) <= 27.6 and 83.4 <= float(lon) <= 94.2


def classify(
    lat: float | None = None,
    lon: float | None = None,
    *,
    state: str | None = None,
    district: str | None = None,
    place: str | None = None,
    coast_km: float | None = None,
    loc: Any = None,
) -> dict[str, Any]:
    if loc is not None:
        state = getattr(loc, "state", None) or state
        district = getattr(loc, "district", None) or district
        place = getattr(loc, "place_name", None) or place
        if getattr(loc, "lat", None) is not None:
            lat = float(loc.lat)
        if getattr(loc, "lon", None) is not None:
            lon = float(loc.lon)
    hugli = hugli_relevant(lat, lon, state=state, district=district, place=place)
    kind = "hugli" if hugli else _kind_from_admin(state, district, place)
    if kind is None and lat is not None and lon is not None:
        kind = _kind_from_box(float(lat), float(lon))
    if kind is None and coast_km is not None and float(coast_km) <= 25:
        kind = "coast"
    if kind is None:
        kind = "plateau"
    scale = _POND_SCALE.get(kind, 0.65)
    return {
        "kind": kind,
        "label": _LABEL.get(kind, kind),
        "pond_scale": scale,
        "kal_belt": _kal_belt(kind, state, lat, lon),
        "hugli": hugli,
        "show_tide": hugli,
        "cwc_max_km": 100.0,
    }

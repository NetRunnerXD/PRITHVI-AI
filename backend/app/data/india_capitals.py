"""Official / working weather point for every Indian state and UT.

Used when the human names a state or city-state (Delhi, Chandigarh, Goa).
This is the weather HQ, not a ranking of districts.
"""

from __future__ import annotations

# query fold → name, district, state, lat, lon, kind
# Coordinates are the usual HQ / Secretariat city, not a random district.
_CAPITALS: dict[str, dict] = {
    "andaman and nicobar": {
        "name": "Port Blair", "district": "South Andaman",
        "state": "Andaman and Nicobar", "lat": 11.6234, "lon": 92.7265, "kind": "city",
    },
    "andhra pradesh": {
        "name": "Amaravati", "district": "Guntur",
        "state": "Andhra Pradesh", "lat": 16.5418, "lon": 80.5150, "kind": "city",
    },
    "arunachal pradesh": {
        "name": "Itanagar", "district": "Papum Pare",
        "state": "Arunachal Pradesh", "lat": 27.0844, "lon": 93.6053, "kind": "city",
    },
    "assam": {
        "name": "Guwahati", "district": "Kamrup Metropolitan",
        "state": "Assam", "lat": 26.1445, "lon": 91.7362, "kind": "city",
    },
    "bihar": {
        "name": "Patna", "district": "Patna",
        "state": "Bihar", "lat": 25.5941, "lon": 85.1376, "kind": "city",
    },
    "chandigarh": {
        "name": "Chandigarh", "district": "Chandigarh",
        "state": "Chandigarh", "lat": 30.7333, "lon": 76.7794, "kind": "city",
    },
    "chhattisgarh": {
        "name": "Raipur", "district": "Raipur",
        "state": "Chhattisgarh", "lat": 21.2514, "lon": 81.6296, "kind": "city",
    },
    "dadra and nagar haveli and daman and diu": {
        "name": "Silvassa", "district": "Dadra and Nagar Haveli",
        "state": "Dadra and Nagar Haveli and Daman and Diu", "lat": 20.1809, "lon": 73.0169, "kind": "town",
    },
    "delhi": {
        "name": "Delhi", "district": "New Delhi",
        "state": "Delhi", "lat": 28.6139, "lon": 77.2090, "kind": "city",
    },
    "goa": {
        "name": "Panaji", "district": "North Goa",
        "state": "Goa", "lat": 15.4909, "lon": 73.8278, "kind": "city",
    },
    "gujarat": {
        "name": "Gandhinagar", "district": "Gandhinagar",
        "state": "Gujarat", "lat": 23.2156, "lon": 72.6369, "kind": "city",
    },
    "haryana": {
        "name": "Chandigarh", "district": "Chandigarh",
        "state": "Haryana", "lat": 30.7333, "lon": 76.7794, "kind": "city",
    },
    "himachal pradesh": {
        "name": "Shimla", "district": "Shimla",
        "state": "Himachal Pradesh", "lat": 31.1048, "lon": 77.1734, "kind": "city",
    },
    "jammu and kashmir": {
        "name": "Srinagar", "district": "Srinagar",
        "state": "Jammu and Kashmir", "lat": 34.0837, "lon": 74.7973, "kind": "city",
    },
    "jharkhand": {
        "name": "Ranchi", "district": "Ranchi",
        "state": "Jharkhand", "lat": 23.3441, "lon": 85.3096, "kind": "city",
    },
    "karnataka": {
        "name": "Bengaluru", "district": "Bengaluru Urban",
        "state": "Karnataka", "lat": 12.9716, "lon": 77.5946, "kind": "city",
    },
    "kerala": {
        "name": "Thiruvananthapuram", "district": "Thiruvananthapuram",
        "state": "Kerala", "lat": 8.5241, "lon": 76.9366, "kind": "city",
    },
    "ladakh": {
        "name": "Leh", "district": "Leh",
        "state": "Ladakh", "lat": 34.1526, "lon": 77.5771, "kind": "town",
    },
    "lakshadweep": {
        "name": "Kavaratti", "district": "Kavaratti",
        "state": "Lakshadweep", "lat": 10.5593, "lon": 72.6358, "kind": "town",
    },
    "madhya pradesh": {
        "name": "Bhopal", "district": "Bhopal",
        "state": "Madhya Pradesh", "lat": 23.2599, "lon": 77.4126, "kind": "city",
    },
    "maharashtra": {
        "name": "Mumbai", "district": "Mumbai",
        "state": "Maharashtra", "lat": 19.0760, "lon": 72.8777, "kind": "city",
    },
    "manipur": {
        "name": "Imphal", "district": "Imphal West",
        "state": "Manipur", "lat": 24.8170, "lon": 93.9368, "kind": "city",
    },
    "meghalaya": {
        "name": "Shillong", "district": "East Khasi Hills",
        "state": "Meghalaya", "lat": 25.5788, "lon": 91.8933, "kind": "city",
    },
    "mizoram": {
        "name": "Aizawl", "district": "Aizawl",
        "state": "Mizoram", "lat": 23.7271, "lon": 92.7176, "kind": "city",
    },
    "nagaland": {
        "name": "Kohima", "district": "Kohima",
        "state": "Nagaland", "lat": 25.6751, "lon": 94.1086, "kind": "city",
    },
    "odisha": {
        "name": "Bhubaneswar", "district": "Khordha",
        "state": "Odisha", "lat": 20.2961, "lon": 85.8245, "kind": "city",
    },
    "puducherry": {
        "name": "Puducherry", "district": "Puducherry",
        "state": "Puducherry", "lat": 11.9416, "lon": 79.8083, "kind": "city",
    },
    "punjab": {
        "name": "Chandigarh", "district": "Chandigarh",
        "state": "Punjab", "lat": 30.7333, "lon": 76.7794, "kind": "city",
    },
    "rajasthan": {
        "name": "Jaipur", "district": "Jaipur",
        "state": "Rajasthan", "lat": 26.9124, "lon": 75.7873, "kind": "city",
    },
    "sikkim": {
        "name": "Gangtok", "district": "Gangtok",
        "state": "Sikkim", "lat": 27.3389, "lon": 88.6065, "kind": "city",
    },
    "tamil nadu": {
        "name": "Chennai", "district": "Chennai",
        "state": "Tamil Nadu", "lat": 13.0827, "lon": 80.2707, "kind": "city",
    },
    "telangana": {
        "name": "Hyderabad", "district": "Hyderabad",
        "state": "Telangana", "lat": 17.3850, "lon": 78.4867, "kind": "city",
    },
    "tripura": {
        "name": "Agartala", "district": "West Tripura",
        "state": "Tripura", "lat": 23.8315, "lon": 91.2868, "kind": "city",
    },
    "uttar pradesh": {
        "name": "Lucknow", "district": "Lucknow",
        "state": "Uttar Pradesh", "lat": 26.8467, "lon": 80.9462, "kind": "city",
    },
    "uttarakhand": {
        "name": "Dehradun", "district": "Dehradun",
        "state": "Uttarakhand", "lat": 30.3165, "lon": 78.0322, "kind": "city",
    },
    "west bengal": {
        "name": "Kolkata", "district": "Kolkata",
        "state": "West Bengal", "lat": 22.5726, "lon": 88.3639, "kind": "city",
    },
}

_ALIASES = {
    "wb": "west bengal",
    "bengal": "west bengal",
    "orissa": "odisha",
    "tn": "tamil nadu",
    "up": "uttar pradesh",
    "mp": "madhya pradesh",
    "hp": "himachal pradesh",
    "uk": "uttarakhand",
    "ap": "andhra pradesh",
    "j&k": "jammu and kashmir",
    "a&n": "andaman and nicobar",
    "andaman": "andaman and nicobar",
    "ncr": "delhi",
    "new delhi": "delhi",
    "nct": "delhi",
    "nct of delhi": "delhi",
    "pondicherry": "puducherry",
    "daman": "dadra and nagar haveli and daman and diu",
    "diu": "dadra and nagar haveli and daman and diu",
    "dnh": "dadra and nagar haveli and daman and diu",
    "silvassa": "dadra and nagar haveli and daman and diu",
    "leh": "ladakh",
    "gandhinagar": "gujarat",
    "amaravati": "andhra pradesh",
    "kavaratti": "lakshadweep",
}


def _key(q: str) -> str:
    return (q or "").strip().lower()


def capital_of(q: str | None) -> dict | None:
    """Return the weather HQ for a state / UT name, or None."""
    n = _key(q)
    if not n:
        return None
    n = _ALIASES.get(n, n)
    row = _CAPITALS.get(n)
    return dict(row) if row else None


def all_capital_names() -> list[str]:
    return sorted({r["name"] for r in _CAPITALS.values()})

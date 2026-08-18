"""Well-known Indian cities and towns that are not district HQs.

Used so search works like a weather app (Haldia, Digha, Santiniketan, …).
"""

from __future__ import annotations

# name, state, district, lat, lon, kind, aliases
TOWNS: list[dict] = [
    {"name": "Haldia", "state": "West Bengal", "district": "Purba Medinipur", "lat": 22.0667, "lon": 88.0698, "kind": "city", "aliases": ["haldia port"]},
    {"name": "Cherrapunji", "state": "Meghalaya", "district": "East Khasi Hills", "lat": 25.2702, "lon": 91.7322, "kind": "town", "aliases": ["cherrapunjee", "sohra", "cherra"]},
    {"name": "Shillong", "state": "Meghalaya", "district": "East Khasi Hills", "lat": 25.5788, "lon": 91.8933, "kind": "city", "aliases": []},
    {"name": "Sagar Island", "state": "West Bengal", "district": "South 24 Parganas", "lat": 21.6500, "lon": 88.0500, "kind": "town", "aliases": ["sagar", "gangasagar"]},
    {"name": "Kakdwip", "state": "West Bengal", "district": "South 24 Parganas", "lat": 21.8800, "lon": 88.1800, "kind": "town", "aliases": ["kakadwip"]},
    {"name": "Digha", "state": "West Bengal", "district": "Purba Medinipur", "lat": 21.6264, "lon": 87.5070, "kind": "town", "aliases": []},
    {"name": "Tamluk", "state": "West Bengal", "district": "Purba Medinipur", "lat": 22.3000, "lon": 87.9167, "kind": "town", "aliases": ["tamralipta"]},
    {"name": "Contai", "state": "West Bengal", "district": "Purba Medinipur", "lat": 21.7786, "lon": 87.7517, "kind": "town", "aliases": ["kantai"]},
    {"name": "Kharagpur", "state": "West Bengal", "district": "Paschim Medinipur", "lat": 22.3460, "lon": 87.2320, "kind": "city", "aliases": []},
    {"name": "Midnapore", "state": "West Bengal", "district": "Paschim Medinipur", "lat": 22.4240, "lon": 87.3190, "kind": "city", "aliases": ["medinipur"]},
    {"name": "Durgapur", "state": "West Bengal", "district": "Paschim Bardhaman", "lat": 23.5204, "lon": 87.3119, "kind": "city", "aliases": []},
    {"name": "Asansol", "state": "West Bengal", "district": "Paschim Bardhaman", "lat": 23.6739, "lon": 86.9524, "kind": "city", "aliases": []},
    {"name": "Siliguri", "state": "West Bengal", "district": "Darjeeling", "lat": 26.7271, "lon": 88.3953, "kind": "city", "aliases": []},
    {"name": "Darjeeling", "state": "West Bengal", "district": "Darjeeling", "lat": 27.0360, "lon": 88.2627, "kind": "town", "aliases": []},
    {"name": "Santiniketan", "state": "West Bengal", "district": "Birbhum", "lat": 23.6773, "lon": 87.6852, "kind": "town", "aliases": ["shantiniketan", "bolpur"]},
    {"name": "Bolpur", "state": "West Bengal", "district": "Birbhum", "lat": 23.6626, "lon": 87.6976, "kind": "town", "aliases": []},
    {"name": "Howrah", "state": "West Bengal", "district": "Howrah", "lat": 22.5958, "lon": 88.2636, "kind": "city", "aliases": []},
    {"name": "Salt Lake", "state": "West Bengal", "district": "North 24 Parganas", "lat": 22.5804, "lon": 88.4199, "kind": "city", "aliases": ["bidhannagar", "saltlake"]},
    {"name": "Barrackpore", "state": "West Bengal", "district": "North 24 Parganas", "lat": 22.7676, "lon": 88.3883, "kind": "city", "aliases": ["barrackpur"]},
    {"name": "Kalyani", "state": "West Bengal", "district": "Nadia", "lat": 22.9750, "lon": 88.4344, "kind": "city", "aliases": []},
    {"name": "Krishnanagar", "state": "West Bengal", "district": "Nadia", "lat": 23.4058, "lon": 88.4907, "kind": "city", "aliases": ["krishnagar"]},
    {"name": "Nabadwip", "state": "West Bengal", "district": "Nadia", "lat": 23.4072, "lon": 88.3676, "kind": "town", "aliases": []},
    {"name": "Diamond Harbour", "state": "West Bengal", "district": "South 24 Parganas", "lat": 22.1927, "lon": 88.1840, "kind": "town", "aliases": []},
    {"name": "Malda", "state": "West Bengal", "district": "Malda", "lat": 25.0108, "lon": 88.1411, "kind": "city", "aliases": ["english bazar"]},
    {"name": "Jalpaiguri", "state": "West Bengal", "district": "Jalpaiguri", "lat": 26.5167, "lon": 88.7333, "kind": "city", "aliases": []},
    {"name": "Cooch Behar", "state": "West Bengal", "district": "Cooch Behar", "lat": 26.3239, "lon": 89.4487, "kind": "city", "aliases": ["kochbihar"]},
    {"name": "Serampore", "state": "West Bengal", "district": "Hooghly", "lat": 22.7500, "lon": 88.3400, "kind": "town", "aliases": ["sreerampore"]},
    {"name": "Chandannagar", "state": "West Bengal", "district": "Hooghly", "lat": 22.8644, "lon": 88.3630, "kind": "town", "aliases": ["chandernagore"]},
    {"name": "Navi Mumbai", "state": "Maharashtra", "district": "Thane", "lat": 19.0330, "lon": 73.0297, "kind": "city", "aliases": ["new mumbai"]},
    {"name": "Thane", "state": "Maharashtra", "district": "Thane", "lat": 19.2183, "lon": 72.9781, "kind": "city", "aliases": []},
    {"name": "Pimpri-Chinchwad", "state": "Maharashtra", "district": "Pune", "lat": 18.6298, "lon": 73.7997, "kind": "city", "aliases": ["pimpri", "chinchwad"]},
    {"name": "Whitefield", "state": "Karnataka", "district": "Bengaluru Urban", "lat": 12.9698, "lon": 77.7499, "kind": "town", "aliases": []},
    {"name": "Electronic City", "state": "Karnataka", "district": "Bengaluru Urban", "lat": 12.8456, "lon": 77.6603, "kind": "town", "aliases": []},
    {"name": "Gurgaon", "state": "Haryana", "district": "Gurugram", "lat": 28.4595, "lon": 77.0266, "kind": "city", "aliases": ["gurugram"]},
    {"name": "Noida", "state": "Uttar Pradesh", "district": "Gautam Buddha Nagar", "lat": 28.5355, "lon": 77.3910, "kind": "city", "aliases": []},
    {"name": "Ghaziabad", "state": "Uttar Pradesh", "district": "Ghaziabad", "lat": 28.6692, "lon": 77.4538, "kind": "city", "aliases": []},
    {"name": "Faridabad", "state": "Haryana", "district": "Faridabad", "lat": 28.4089, "lon": 77.3178, "kind": "city", "aliases": []},
    {"name": "Dwarka", "state": "Delhi", "district": "South West Delhi", "lat": 28.5921, "lon": 77.0460, "kind": "city", "aliases": []},
    {"name": "Vashi", "state": "Maharashtra", "district": "Thane", "lat": 19.0771, "lon": 72.9986, "kind": "town", "aliases": []},
    {"name": "Puri", "state": "Odisha", "district": "Puri", "lat": 19.8135, "lon": 85.8312, "kind": "city", "aliases": []},
    {"name": "Paradip", "state": "Odisha", "district": "Jagatsinghpur", "lat": 20.3167, "lon": 86.6100, "kind": "town", "aliases": ["paradeep"]},
    {"name": "Rourkela", "state": "Odisha", "district": "Sundargarh", "lat": 22.2604, "lon": 84.8536, "kind": "city", "aliases": []},
    {"name": "Visakhapatnam", "state": "Andhra Pradesh", "district": "Visakhapatnam", "lat": 17.6868, "lon": 83.2185, "kind": "city", "aliases": ["vizag", "vishakhapatnam"]},
    {"name": "Vijayawada", "state": "Andhra Pradesh", "district": "NTR", "lat": 16.5062, "lon": 80.6480, "kind": "city", "aliases": []},
    {"name": "Coimbatore", "state": "Tamil Nadu", "district": "Coimbatore", "lat": 11.0168, "lon": 76.9558, "kind": "city", "aliases": []},
    {"name": "Madurai", "state": "Tamil Nadu", "district": "Madurai", "lat": 9.9252, "lon": 78.1198, "kind": "city", "aliases": []},
    {"name": "Kochi", "state": "Kerala", "district": "Ernakulam", "lat": 9.9312, "lon": 76.2673, "kind": "city", "aliases": ["cochin", "ernakulam"]},
    {"name": "Thiruvananthapuram", "state": "Kerala", "district": "Thiruvananthapuram", "lat": 8.5241, "lon": 76.9366, "kind": "city", "aliases": ["trivandrum"]},
    {"name": "Mangaluru", "state": "Karnataka", "district": "Dakshina Kannada", "lat": 12.9141, "lon": 74.8560, "kind": "city", "aliases": ["mangalore"]},
    {"name": "Mysuru", "state": "Karnataka", "district": "Mysuru", "lat": 12.2958, "lon": 76.6394, "kind": "city", "aliases": ["mysore"]},
    {"name": "Indore", "state": "Madhya Pradesh", "district": "Indore", "lat": 22.7196, "lon": 75.8577, "kind": "city", "aliases": []},
    {"name": "Bhopal", "state": "Madhya Pradesh", "district": "Bhopal", "lat": 23.2599, "lon": 77.4126, "kind": "city", "aliases": []},
    {"name": "Jaipur", "state": "Rajasthan", "district": "Jaipur", "lat": 26.9124, "lon": 75.7873, "kind": "city", "aliases": []},
    {"name": "Ahmedabad", "state": "Gujarat", "district": "Ahmedabad", "lat": 23.0225, "lon": 72.5714, "kind": "city", "aliases": []},
    {"name": "Surat", "state": "Gujarat", "district": "Surat", "lat": 21.1702, "lon": 72.8311, "kind": "city", "aliases": []},
    {"name": "Vadodara", "state": "Gujarat", "district": "Vadodara", "lat": 22.3072, "lon": 73.1812, "kind": "city", "aliases": ["baroda"]},
    {"name": "Lucknow", "state": "Uttar Pradesh", "district": "Lucknow", "lat": 26.8467, "lon": 80.9462, "kind": "city", "aliases": []},
    {"name": "Kanpur", "state": "Uttar Pradesh", "district": "Kanpur Nagar", "lat": 26.4499, "lon": 80.3319, "kind": "city", "aliases": []},
    {"name": "Varanasi", "state": "Uttar Pradesh", "district": "Varanasi", "lat": 25.3176, "lon": 82.9739, "kind": "city", "aliases": ["benares", "kashi"]},
    {"name": "Patna", "state": "Bihar", "district": "Patna", "lat": 25.5941, "lon": 85.1376, "kind": "city", "aliases": []},
    {"name": "Ranchi", "state": "Jharkhand", "district": "Ranchi", "lat": 23.3441, "lon": 85.3096, "kind": "city", "aliases": []},
    {"name": "Jamshedpur", "state": "Jharkhand", "district": "East Singhbhum", "lat": 22.8046, "lon": 86.2029, "kind": "city", "aliases": []},
    {"name": "Guwahati", "state": "Assam", "district": "Kamrup Metropolitan", "lat": 26.1445, "lon": 91.7362, "kind": "city", "aliases": ["gauhati"]},
    {"name": "Bhubaneswar", "state": "Odisha", "district": "Khordha", "lat": 20.2961, "lon": 85.8245, "kind": "city", "aliases": []},
    {"name": "Chandigarh", "state": "Chandigarh", "district": "Chandigarh", "lat": 30.7333, "lon": 76.7794, "kind": "city", "aliases": []},
    {"name": "Amritsar", "state": "Punjab", "district": "Amritsar", "lat": 31.6340, "lon": 74.8723, "kind": "city", "aliases": []},
    {"name": "Srinagar", "state": "Jammu and Kashmir", "district": "Srinagar", "lat": 34.0837, "lon": 74.7973, "kind": "city", "aliases": []},
    {"name": "Port Blair", "state": "Andaman and Nicobar", "district": "South Andaman", "lat": 11.6234, "lon": 92.7265, "kind": "city", "aliases": []},
]


def extract_towns(text: str) -> list[str]:
    """All curated towns mentioned, longest match first. Fuzzy on tokens."""
    import re

    from app.data.fuzzy import close_enough, tokens

    blob = (text or "").lower()
    found: dict[str, int] = {}
    for t in TOWNS:
        names = [t["name"], *t.get("aliases", [])]
        for n in names:
            key = (n or "").strip().lower()
            if len(key) < 4:
                continue
            if re.search(rf"(?<![a-z]){re.escape(key)}(?![a-z])", blob):
                found[t["name"]] = max(found.get(t["name"], 0), len(key))
    if not found:
        for tok in tokens(text or ""):
            for t in TOWNS:
                names = [t["name"], *t.get("aliases", [])]
                if any(close_enough(tok, n) for n in names if n):
                    found[t["name"]] = max(found.get(t["name"], 0), len(tok))
    return [name for name, _ in sorted(found.items(), key=lambda x: -x[1])]


def extract_town(text: str) -> str | None:
    """Longest town / alias mentioned in free text (Haldia, not the district)."""
    hits = extract_towns(text)
    return hits[0] if hits else None


def search_towns(q: str, limit: int = 8) -> list[dict]:
    from app.data.fuzzy import close_enough, match_rank

    needle = (q or "").strip().lower()
    if not needle:
        return []
    scored: list[tuple[int, dict]] = []
    for t in TOWNS:
        names = [t["name"].lower(), *(a.lower() for a in t["aliases"])]
        ranks = [match_rank(needle, n) for n in names]
        ranks = [r for r in ranks if r is not None]
        if needle in names:
            scored.append((0, t))
        elif ranks and min(ranks) == 0:
            scored.append((1, t))
        elif any(
            n.startswith(needle) and len(needle) >= 4 and 0 < len(n) - len(needle) <= 2
            for n in names
        ):
            # "chenna" → Chennai. NOT "puruliya" → Puri (longer query, shorter name).
            scored.append((2, t))
        elif ranks:
            scored.append((3, t))
        elif any(close_enough(needle, n) for n in names):
            scored.append((3, t))
        elif any(len(needle) >= 6 and needle in n for n in names):
            scored.append((4, t))
    scored.sort(key=lambda x: (x[0], x[1]["name"]))
    return [t for _, t in scored[:limit]]

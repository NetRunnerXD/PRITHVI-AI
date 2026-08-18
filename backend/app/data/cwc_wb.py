"""Documented CWC / Hugli flood stations. Not a live gauge API."""

STATIONS: list[dict] = [
    {"id": "cwc_haldia", "name": "Haldia", "river": "Hugli", "lat": 22.0667, "lon": 88.0698},
    {"id": "cwc_diamond", "name": "Diamond Harbour", "river": "Hugli", "lat": 22.1927, "lon": 88.1840},
    {"id": "cwc_garden", "name": "Garden Reach", "river": "Hugli", "lat": 22.5470, "lon": 88.2900},
    {"id": "cwc_farakka", "name": "Farakka", "river": "Ganga", "lat": 24.8000, "lon": 87.9200},
    {"id": "cwc_nabadwip", "name": "Nabadwip", "river": "Bhagirathi", "lat": 23.4072, "lon": 88.3676},
    {"id": "cwc_berhampore", "name": "Berhampore", "river": "Bhagirathi", "lat": 24.1000, "lon": 88.2500},
    {"id": "cwc_gangtok_teesta", "name": "Domohani", "river": "Teesta", "lat": 26.5700, "lon": 88.7600},
]


def nearest(lat: float, lon: float) -> dict:
    best = STATIONS[0]
    best_d = 1e9
    for s in STATIONS:
        d = (s["lat"] - lat) ** 2 + (s["lon"] - lon) ** 2
        if d < best_d:
            best, best_d = s, d
    km = (best_d ** 0.5) * 111.3
    return {**best, "km": round(km, 1), "note": "Nearest documented station. Not a live CWC hydrograph."}

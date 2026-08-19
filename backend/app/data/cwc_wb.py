"""Documented CWC / flood stations. Not a live gauge API.

Hugli–Ganga plus a short national list so Pune is not labelled Farakka.
`relevant` is false when the nearest named station is too far to matter.
"""

MAX_SHOW_KM = 100.0

STATIONS: list[dict] = [
    {"id": "cwc_haldia", "name": "Haldia", "river": "Hugli", "lat": 22.0667, "lon": 88.0698},
    {"id": "cwc_diamond", "name": "Diamond Harbour", "river": "Hugli", "lat": 22.1927, "lon": 88.1840},
    {"id": "cwc_garden", "name": "Garden Reach", "river": "Hugli", "lat": 22.5470, "lon": 88.2900},
    {"id": "cwc_farakka", "name": "Farakka", "river": "Ganga", "lat": 24.8000, "lon": 87.9200},
    {"id": "cwc_nabadwip", "name": "Nabadwip", "river": "Bhagirathi", "lat": 23.4072, "lon": 88.3676},
    {"id": "cwc_berhampore", "name": "Berhampore", "river": "Bhagirathi", "lat": 24.1000, "lon": 88.2500},
    {"id": "cwc_gangtok_teesta", "name": "Domohani", "river": "Teesta", "lat": 26.5700, "lon": 88.7600},
    {"id": "cwc_patna", "name": "Patna", "river": "Ganga", "lat": 25.61, "lon": 85.14},
    {"id": "cwc_varanasi", "name": "Varanasi", "river": "Ganga", "lat": 25.32, "lon": 83.01},
    {"id": "cwc_prayagraj", "name": "Prayagraj", "river": "Ganga", "lat": 25.44, "lon": 81.85},
    {"id": "cwc_kanpur", "name": "Kanpur", "river": "Ganga", "lat": 26.45, "lon": 80.33},
    {"id": "cwc_haridwar", "name": "Haridwar", "river": "Ganga", "lat": 29.945, "lon": 78.164},
    {"id": "cwc_delhi", "name": "Delhi", "river": "Yamuna", "lat": 28.66, "lon": 77.23},
    {"id": "cwc_lucknow", "name": "Lucknow", "river": "Gomti", "lat": 26.85, "lon": 80.95},
    {"id": "cwc_guwahati", "name": "Guwahati", "river": "Brahmaputra", "lat": 26.18, "lon": 91.75},
    {"id": "cwc_dibrugarh", "name": "Dibrugarh", "river": "Brahmaputra", "lat": 27.47, "lon": 94.91},
    {"id": "cwc_naraj", "name": "Naraj", "river": "Mahanadi", "lat": 20.47, "lon": 85.77},
    {"id": "cwc_vijayawada", "name": "Vijayawada", "river": "Krishna", "lat": 16.51, "lon": 80.62},
    {"id": "cwc_rajahmundry", "name": "Rajahmundry", "river": "Godavari", "lat": 16.99, "lon": 81.78},
    {"id": "cwc_nashik", "name": "Nashik", "river": "Godavari", "lat": 19.99, "lon": 73.78},
    {"id": "cwc_pune", "name": "Pune", "river": "Mutha", "lat": 18.52, "lon": 73.86},
    {"id": "cwc_surat", "name": "Surat", "river": "Tapi", "lat": 21.17, "lon": 72.83},
    {"id": "cwc_bharuch", "name": "Bharuch", "river": "Narmada", "lat": 21.70, "lon": 72.99},
    {"id": "cwc_ahmedabad", "name": "Ahmedabad", "river": "Sabarmati", "lat": 23.03, "lon": 72.58},
    {"id": "cwc_kota", "name": "Kota", "river": "Chambal", "lat": 25.18, "lon": 75.83},
    {"id": "cwc_srinagar", "name": "Srinagar", "river": "Jhelum", "lat": 34.08, "lon": 74.80},
    {"id": "cwc_hyderabad", "name": "Hyderabad", "river": "Musi", "lat": 17.38, "lon": 78.48},
    {"id": "cwc_trichy", "name": "Tiruchirappalli", "river": "Cauvery", "lat": 10.81, "lon": 78.69},
    {"id": "cwc_chennai", "name": "Chennai", "river": "Adyar", "lat": 13.05, "lon": 80.25},
    {"id": "cwc_kochi", "name": "Kochi", "river": "Periyar", "lat": 10.00, "lon": 76.27},
    {"id": "cwc_panaji", "name": "Panaji", "river": "Mandovi", "lat": 15.50, "lon": 73.83},
]


def nearest(lat: float, lon: float) -> dict:
    best = STATIONS[0]
    best_d = 1e9
    for s in STATIONS:
        d = (s["lat"] - lat) ** 2 + (s["lon"] - lon) ** 2
        if d < best_d:
            best, best_d = s, d
    km = round((best_d ** 0.5) * 111.3, 1)
    return {
        **best,
        "km": km,
        "relevant": km <= MAX_SHOW_KM,
        "note": "Nearest documented station. Not a live CWC hydrograph.",
    }

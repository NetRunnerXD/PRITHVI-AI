"""Gazetteer of Indian districts used for search, IMD-style labels, and default focus.

Coordinates are district HQ / centroid approximations. Search is substring + alias.
"""

from __future__ import annotations

import re
from functools import lru_cache

# id, label, state, district, subdivision, lat, lon, aliases, crop_hint
_RAW: list[tuple] = [
    # West Bengal / Gangetic
    ("in_wb_nadia", "Nadia, West Bengal", "West Bengal", "Nadia", "Gangetic West Bengal", 23.4710, 88.5565, "krishnanagar,kalyani", "aman_rice"),
    ("in_wb_kolkata", "Kolkata, West Bengal", "West Bengal", "Kolkata", "Gangetic West Bengal", 22.5726, 88.3639, "calcutta,calcuta,kolkatta", "vegetables"),
    ("in_wb_n24p", "North 24 Parganas, West Bengal", "West Bengal", "North 24 Parganas", "Gangetic West Bengal", 22.7245, 88.4805, "barasat,bongaon", "aman_rice"),
    ("in_wb_s24p", "South 24 Parganas, West Bengal", "West Bengal", "South 24 Parganas", "Gangetic West Bengal", 22.1352, 88.4016, "baruipur,sundarban", "aman_rice"),
    ("in_wb_howrah", "Howrah, West Bengal", "West Bengal", "Howrah", "Gangetic West Bengal", 22.5958, 88.2636, "haora", "vegetables"),
    ("in_wb_hooghly", "Hooghly, West Bengal", "West Bengal", "Hooghly", "Gangetic West Bengal", 22.8963, 88.4025, "chinsurah,hooghlly", "aman_rice"),
    ("in_wb_murshidabad", "Murshidabad, West Bengal", "West Bengal", "Murshidabad", "Gangetic West Bengal", 24.1759, 88.2802, "berhampore", "aman_rice"),
    ("in_wb_malda", "Malda, West Bengal", "West Bengal", "Malda", "Gangetic West Bengal", 25.0108, 88.1411, "english bazar", "mango"),
    ("in_wb_eburdwan", "Purba Bardhaman, West Bengal", "West Bengal", "Purba Bardhaman", "Gangetic West Bengal", 23.2324, 87.8615, "bardhaman,burdwan", "aman_rice"),
    ("in_wb_birbhum", "Birbhum, West Bengal", "West Bengal", "Birbhum", "Gangetic West Bengal", 23.8400, 87.6186, "suri", "aman_rice"),
    ("in_wb_bankura", "Bankura, West Bengal", "West Bengal", "Bankura", "Gangetic West Bengal", 23.2324, 87.0786, "", "aman_rice"),
    ("in_wb_purulia", "Purulia, West Bengal", "West Bengal", "Purulia", "Gangetic West Bengal", 23.3321, 86.3652, "puruliya,purulia district", "maize"),
    ("in_wb_eastmed", "Paschim Medinipur, West Bengal", "West Bengal", "Paschim Medinipur", "Gangetic West Bengal", 22.4250, 87.3190, "midnapore,west midnapore", "aman_rice"),
    ("in_wb_jalpaiguri", "Jalpaiguri, West Bengal", "West Bengal", "Jalpaiguri", "Sub Himalayan West Bengal", 26.5435, 88.7201, "", "tea"),
    ("in_wb_darjeeling", "Darjeeling, West Bengal", "West Bengal", "Darjeeling", "Sub Himalayan West Bengal", 27.0360, 88.2627, "siliguri", "tea"),
    ("in_wb_alipurduar", "Alipurduar, West Bengal", "West Bengal", "Alipurduar", "Sub Himalayan West Bengal", 26.4910, 89.5270, "", "tea"),
    ("in_wb_cooch", "Cooch Behar, West Bengal", "West Bengal", "Cooch Behar", "Sub Himalayan West Bengal", 26.3239, 89.4510, "koch bihar", "jute"),
    ("in_wb_kalimpong", "Kalimpong, West Bengal", "West Bengal", "Kalimpong", "Sub Himalayan West Bengal", 27.0700, 88.4750, "", "cardamom"),
    ("in_wb_udinajpur", "Uttar Dinajpur, West Bengal", "West Bengal", "Uttar Dinajpur", "Sub Himalayan West Bengal", 25.6170, 88.1240, "raiganj", "rice"),
    ("in_wb_ddinajpur", "Dakshin Dinajpur, West Bengal", "West Bengal", "Dakshin Dinajpur", "Gangetic West Bengal", 25.2210, 88.7630, "balurghat", "rice"),
    ("in_wb_wburdwan", "Paschim Bardhaman, West Bengal", "West Bengal", "Paschim Bardhaman", "Gangetic West Bengal", 23.6730, 87.6850, "asansol,durgapur", "vegetables"),
    ("in_wb_eastmedinipur", "Purba Medinipur, West Bengal", "West Bengal", "Purba Medinipur", "Gangetic West Bengal", 22.3010, 87.9160, "tamluk,haldia", "aman_rice"),
    ("in_wb_jhargram", "Jhargram, West Bengal", "West Bengal", "Jhargram", "Gangetic West Bengal", 22.4540, 86.9970, "", "sal"),
    # Odisha
    ("in_od_khordha", "Khordha, Odisha", "Odisha", "Khordha", "Odisha", 20.1820, 85.6160, "bhubaneswar", "rice"),
    ("in_od_cuttack", "Cuttack, Odisha", "Odisha", "Cuttack", "Odisha", 20.4625, 85.8830, "", "rice"),
    ("in_od_puri", "Puri, Odisha", "Odisha", "Puri", "Odisha", 19.8135, 85.8312, "", "rice"),
    ("in_od_baleswar", "Balasore, Odisha", "Odisha", "Balasore", "Odisha", 21.4942, 86.9336, "baleshwar", "rice"),
    ("in_od_mayurbhanj", "Mayurbhanj, Odisha", "Odisha", "Mayurbhanj", "Odisha", 21.9270, 86.7370, "baripada", "rice"),
    ("in_od_ganjam", "Ganjam, Odisha", "Odisha", "Ganjam", "Odisha", 19.3540, 84.9860, "berhampur", "rice"),
    ("in_od_sambalpur", "Sambalpur, Odisha", "Odisha", "Sambalpur", "Odisha", 21.4669, 83.9812, "", "rice"),
    # Jharkhand / Bihar / Chhattisgarh (active monsoon belt)
    ("in_jh_ranchi", "Ranchi, Jharkhand", "Jharkhand", "Ranchi", "Jharkhand", 23.3441, 85.3096, "", "rice"),
    ("in_jh_eastsing", "East Singhbhum, Jharkhand", "Jharkhand", "East Singhbhum", "Jharkhand", 22.8046, 86.2029, "jamshedpur", "vegetables"),
    ("in_jh_dhanbad", "Dhanbad, Jharkhand", "Jharkhand", "Dhanbad", "Jharkhand", 23.7957, 86.4304, "", "vegetables"),
    ("in_br_patna", "Patna, Bihar", "Bihar", "Patna", "Bihar", 25.5941, 85.1376, "", "rice"),
    ("in_br_muzaffarpur", "Muzaffarpur, Bihar", "Bihar", "Muzaffarpur", "Bihar", 26.1209, 85.3647, "", "litchi"),
    ("in_br_darbhanga", "Darbhanga, Bihar", "Bihar", "Darbhanga", "Bihar", 26.1542, 85.8918, "", "rice"),
    ("in_br_gaya", "Gaya, Bihar", "Bihar", "Gaya", "Bihar", 24.7969, 85.0039, "", "rice"),
    ("in_br_bhagalpur", "Bhagalpur, Bihar", "Bihar", "Bhagalpur", "Bihar", 25.2425, 86.9842, "", "rice"),
    ("in_cg_raipur", "Raipur, Chhattisgarh", "Chhattisgarh", "Raipur", "Chhattisgarh", 21.2514, 81.6296, "", "rice"),
    ("in_cg_bilaspur", "Bilaspur, Chhattisgarh", "Chhattisgarh", "Bilaspur", "Chhattisgarh", 22.0796, 82.1391, "", "rice"),
    ("in_cg_durg", "Durg, Chhattisgarh", "Chhattisgarh", "Durg", "Chhattisgarh", 21.1904, 81.2849, "bhilai", "rice"),
    # East / Northeast
    ("in_as_kamrupm", "Kamrup Metropolitan, Assam", "Assam", "Kamrup Metropolitan", "Assam", 26.1445, 91.7362, "guwahati", "rice"),
    ("in_as_jorhat", "Jorhat, Assam", "Assam", "Jorhat", "Assam", 26.7509, 94.2037, "", "tea"),
    ("in_as_dibrugarh", "Dibrugarh, Assam", "Assam", "Dibrugarh", "Assam", 27.4728, 94.9120, "", "tea"),
    ("in_as_cachar", "Cachar, Assam", "Assam", "Cachar", "Assam", 24.8333, 92.7789, "silchar", "rice"),
    ("in_ml_eastkhasi", "East Khasi Hills, Meghalaya", "Meghalaya", "East Khasi Hills", "Meghalaya", 25.5788, 91.8933, "shillong", "vegetables"),
    ("in_tr_west", "West Tripura, Tripura", "Tripura", "West Tripura", "Tripura", 23.8315, 91.2868, "agartala", "rice"),
    ("in_mn_imphalw", "Imphal West, Manipur", "Manipur", "Imphal West", "Manipur", 24.8170, 93.9368, "imphal", "rice"),
    ("in_nl_kohima", "Kohima, Nagaland", "Nagaland", "Kohima", "Nagaland", 25.6751, 94.1086, "", "rice"),
    ("in_mz_aizawl", "Aizawl, Mizoram", "Mizoram", "Aizawl", "Mizoram", 23.7271, 92.7176, "", "rice"),
    ("in_ar_itanagar", "Papum Pare, Arunachal Pradesh", "Arunachal Pradesh", "Papum Pare", "Arunachal Pradesh", 27.0844, 93.6053, "itanagar", "rice"),
    ("in_sk_east", "Gangtok, Sikkim", "Sikkim", "Gangtok", "Sikkim", 27.3389, 88.6065, "east sikkim", "cardamom"),
    # Indo-Gangetic / North
    ("in_up_lucknow", "Lucknow, Uttar Pradesh", "Uttar Pradesh", "Lucknow", "East Uttar Pradesh", 26.8467, 80.9462, "", "wheat"),
    ("in_up_varanasi", "Varanasi, Uttar Pradesh", "Uttar Pradesh", "Varanasi", "East Uttar Pradesh", 25.3176, 82.9739, "banaras,kashi", "wheat"),
    ("in_up_prayagraj", "Prayagraj, Uttar Pradesh", "Uttar Pradesh", "Prayagraj", "East Uttar Pradesh", 25.4358, 81.8463, "allahabad", "wheat"),
    ("in_up_kanpur", "Kanpur Nagar, Uttar Pradesh", "Uttar Pradesh", "Kanpur Nagar", "East Uttar Pradesh", 26.4499, 80.3319, "kanpur", "wheat"),
    ("in_up_gorakhpur", "Gorakhpur, Uttar Pradesh", "Uttar Pradesh", "Gorakhpur", "East Uttar Pradesh", 26.7606, 83.3732, "", "wheat"),
    ("in_up_agra", "Agra, Uttar Pradesh", "Uttar Pradesh", "Agra", "West Uttar Pradesh", 27.1767, 78.0081, "", "wheat"),
    ("in_up_meerut", "Meerut, Uttar Pradesh", "Uttar Pradesh", "Meerut", "West Uttar Pradesh", 28.9845, 77.7064, "", "sugarcane"),
    ("in_dl_newdelhi", "New Delhi, Delhi", "Delhi", "New Delhi", "Delhi", 28.6139, 77.2090, "delhi,ncr", "vegetables"),
    ("in_hr_gurugram", "Gurugram, Haryana", "Haryana", "Gurugram", "Haryana", 28.4595, 77.0266, "gurgaon", "wheat"),
    ("in_hr_karnal", "Karnal, Haryana", "Haryana", "Karnal", "Haryana", 29.6857, 76.9905, "", "wheat"),
    ("in_hr_hisar", "Hisar, Haryana", "Haryana", "Hisar", "Haryana", 29.1492, 75.7217, "", "wheat"),
    ("in_pb_ludhiana", "Ludhiana, Punjab", "Punjab", "Ludhiana", "Punjab", 30.9010, 75.8573, "", "wheat"),
    ("in_pb_amritsar", "Amritsar, Punjab", "Punjab", "Amritsar", "Punjab", 31.6340, 74.8723, "", "wheat"),
    ("in_pb_patiala", "Patiala, Punjab", "Punjab", "Patiala", "Punjab", 30.3398, 76.3869, "", "wheat"),
    ("in_pb_bathinda", "Bathinda, Punjab", "Punjab", "Bathinda", "Punjab", 30.2110, 74.9455, "", "cotton"),
    ("in_uk_dehradun", "Dehradun, Uttarakhand", "Uttarakhand", "Dehradun", "Uttarakhand", 30.3165, 78.0322, "", "wheat"),
    ("in_hp_shimla", "Shimla, Himachal Pradesh", "Himachal Pradesh", "Shimla", "Himachal Pradesh", 31.1048, 77.1734, "", "apple"),
    ("in_jk_srinagar", "Srinagar, Jammu and Kashmir", "Jammu and Kashmir", "Srinagar", "Jammu and Kashmir", 34.0837, 74.7973, "", "apple"),
    ("in_jk_jammu", "Jammu, Jammu and Kashmir", "Jammu and Kashmir", "Jammu", "Jammu and Kashmir", 32.7266, 74.8570, "", "wheat"),
    # West / Central
    ("in_rj_jaipur", "Jaipur, Rajasthan", "Rajasthan", "Jaipur", "East Rajasthan", 26.9124, 75.7873, "", "wheat"),
    ("in_rj_jodhpur", "Jodhpur, Rajasthan", "Rajasthan", "Jodhpur", "West Rajasthan", 26.2389, 73.0243, "", "millet"),
    ("in_rj_udaipur", "Udaipur, Rajasthan", "Rajasthan", "Udaipur", "East Rajasthan", 24.5854, 73.7125, "", "maize"),
    ("in_rj_bikaner", "Bikaner, Rajasthan", "Rajasthan", "Bikaner", "West Rajasthan", 28.0229, 73.3119, "", "millet"),
    ("in_rj_kota", "Kota, Rajasthan", "Rajasthan", "Kota", "East Rajasthan", 25.2138, 75.8648, "", "soybean"),
    ("in_gj_ahmedabad", "Ahmedabad, Gujarat", "Gujarat", "Ahmedabad", "Gujarat", 23.0225, 72.5714, "", "cotton"),
    ("in_gj_surat", "Surat, Gujarat", "Gujarat", "Surat", "Gujarat", 21.1702, 72.8311, "", "sugarcane"),
    ("in_gj_rajkot", "Rajkot, Gujarat", "Gujarat", "Rajkot", "Saurashtra", 22.3039, 70.8022, "", "groundnut"),
    ("in_gj_kutch", "Kachchh, Gujarat", "Gujarat", "Kachchh", "Saurashtra", 23.2420, 69.6669, "bhuj,kutch", "groundnut"),
    ("in_mh_mumbai", "Mumbai, Maharashtra", "Maharashtra", "Mumbai", "Konkan", 19.0760, 72.8777, "bombay", "vegetables"),
    ("in_mh_pune", "Pune, Maharashtra", "Maharashtra", "Pune", "Madhya Maharashtra", 18.5204, 73.8567, "", "sugarcane"),
    ("in_mh_nagpur", "Nagpur, Maharashtra", "Maharashtra", "Nagpur", "Vidarbha", 21.1458, 79.0882, "", "cotton"),
    ("in_mh_nashik", "Nashik, Maharashtra", "Maharashtra", "Nashik", "Madhya Maharashtra", 19.9975, 73.7898, "", "grapes"),
    ("in_mh_aurangabad", "Chhatrapati Sambhajinagar, Maharashtra", "Maharashtra", "Chhatrapati Sambhajinagar", "Marathwada", 19.8762, 75.3433, "aurangabad", "cotton"),
    ("in_mh_solapur", "Solapur, Maharashtra", "Maharashtra", "Solapur", "Madhya Maharashtra", 17.6599, 75.9064, "", "sugarcane"),
    ("in_mp_bhopal", "Bhopal, Madhya Pradesh", "Madhya Pradesh", "Bhopal", "West Madhya Pradesh", 23.2599, 77.4126, "", "soybean"),
    ("in_mp_indore", "Indore, Madhya Pradesh", "Madhya Pradesh", "Indore", "West Madhya Pradesh", 22.7196, 75.8577, "", "soybean"),
    ("in_mp_jabalpur", "Jabalpur, Madhya Pradesh", "Madhya Pradesh", "Jabalpur", "East Madhya Pradesh", 23.1815, 79.9864, "", "wheat"),
    ("in_mp_gwalior", "Gwalior, Madhya Pradesh", "Madhya Pradesh", "Gwalior", "West Madhya Pradesh", 26.2183, 78.1828, "", "wheat"),
    ("in_ga_north", "North Goa, Goa", "Goa", "North Goa", "Goa", 15.4909, 73.8278, "panaji", "rice"),
    # South
    ("in_ka_bengaluru", "Bengaluru Urban, Karnataka", "Karnataka", "Bengaluru Urban", "South Interior Karnataka", 12.9716, 77.5946, "bangalore,bengaluru", "vegetables"),
    ("in_ka_mysuru", "Mysuru, Karnataka", "Karnataka", "Mysuru", "South Interior Karnataka", 12.2958, 76.6394, "mysore", "ragi"),
    ("in_ka_dharwad", "Dharwad, Karnataka", "Karnataka", "Dharwad", "North Interior Karnataka", 15.4589, 75.0078, "hubballi", "cotton"),
    ("in_ka_dakshina", "Dakshina Kannada, Karnataka", "Karnataka", "Dakshina Kannada", "Coastal Karnataka", 12.9141, 74.8560, "mangaluru,mangalore", "arecanut"),
    ("in_tn_chennai", "Chennai, Tamil Nadu", "Tamil Nadu", "Chennai", "Tamil Nadu", 13.0827, 80.2707, "madras", "vegetables"),
    ("in_tn_coimbatore", "Coimbatore, Tamil Nadu", "Tamil Nadu", "Coimbatore", "Tamil Nadu", 11.0168, 76.9558, "", "cotton"),
    ("in_tn_madurai", "Madurai, Tamil Nadu", "Tamil Nadu", "Madurai", "Tamil Nadu", 9.9252, 78.1198, "", "rice"),
    ("in_tn_thanjavur", "Thanjavur, Tamil Nadu", "Tamil Nadu", "Thanjavur", "Tamil Nadu", 10.7870, 79.1378, "tanjore", "rice"),
    ("in_kl_ernakulam", "Ernakulam, Kerala", "Kerala", "Ernakulam", "Kerala", 9.9816, 76.2999, "kochi,cochin", "coconut"),
    ("in_kl_tvm", "Thiruvananthapuram, Kerala", "Kerala", "Thiruvananthapuram", "Kerala", 8.5241, 76.9366, "trivandrum", "coconut"),
    ("in_kl_kozhikode", "Kozhikode, Kerala", "Kerala", "Kozhikode", "Kerala", 11.2588, 75.7804, "calicut", "coconut"),
    ("in_kl_wayanad", "Wayanad, Kerala", "Kerala", "Wayanad", "Kerala", 11.6854, 76.1320, "", "coffee"),
    ("in_ap_visakhapatnam", "Visakhapatnam, Andhra Pradesh", "Andhra Pradesh", "Visakhapatnam", "Coastal Andhra", 17.6868, 83.2185, "vizag", "rice"),
    ("in_ap_guntur", "Guntur, Andhra Pradesh", "Andhra Pradesh", "Guntur", "Coastal Andhra", 16.3067, 80.4365, "", "chilli"),
    ("in_ap_anantapur", "Anantapur, Andhra Pradesh", "Andhra Pradesh", "Anantapur", "Rayalaseema", 14.6819, 77.6006, "", "groundnut"),
    ("in_ts_hyderabad", "Hyderabad, Telangana", "Telangana", "Hyderabad", "Telangana", 17.3850, 78.4867, "", "vegetables"),
    ("in_ts_warangal", "Warangal, Telangana", "Telangana", "Warangal", "Telangana", 17.9689, 79.5941, "", "cotton"),
    ("in_ts_nizamabad", "Nizamabad, Telangana", "Telangana", "Nizamabad", "Telangana", 18.6725, 78.0941, "", "rice"),
    ("in_py_puducherry", "Puducherry, Puducherry", "Puducherry", "Puducherry", "Tamil Nadu", 11.9416, 79.8083, "pondicherry", "rice"),
    # Islands / UTs
    ("in_an_south", "South Andaman, A&N Islands", "Andaman and Nicobar", "South Andaman", "A&N Islands", 11.6234, 92.7265, "port blair", "coconut"),
    ("in_ld_kavaratti", "Kavaratti, Lakshadweep", "Lakshadweep", "Kavaratti", "Lakshadweep", 10.5593, 72.6358, "", "coconut"),
    ("in_ch_chandigarh", "Chandigarh, Chandigarh", "Chandigarh", "Chandigarh", "Punjab", 30.7333, 76.7794, "", "vegetables"),
    ("in_dn_dnh", "Dadra and Nagar Haveli, DNHDD", "Dadra and Nagar Haveli and Daman and Diu", "Dadra and Nagar Haveli", "Gujarat", 20.1809, 73.0169, "silvassa", "rice"),
]


def _row(t: tuple) -> dict:
    return {
        "id": t[0],
        "label": t[1],
        "state": t[2],
        "district": t[3],
        "imd_subdivision": t[4],
        "lat": t[5],
        "lon": t[6],
        "aliases": [a.strip() for a in t[7].split(",") if a.strip()],
        "crop_hint": t[8],
        "country": "IN",
        "timezone": "Asia/Kolkata",
    }


@lru_cache
def all_districts() -> list[dict]:
    return [_row(t) for t in _RAW]


def default_district() -> dict:
    return next(d for d in all_districts() if d["id"] == "in_wb_nadia")


def search_districts(q: str, limit: int = 8) -> list[dict]:
    from app.data.fuzzy import close_enough, fold, match_rank, ratio

    needle = (q or "").strip().lower()
    if not needle:
        return all_districts()[:limit]
    # A bare state name must not blob-match every district (Odisha ≠ Balasore).
    # Alias hits still count: "delhi" → New Delhi.
    scored: list[tuple[int, dict]] = []
    for d in all_districts():
        names = [d["district"], *d["aliases"], d["label"]]
        blob = " ".join([d["district"], d["state"], d["label"], d["id"], *d["aliases"]]).lower()
        ranks = [match_rank(needle, n) for n in names if n]
        ranks = [r for r in ranks if r is not None]
        if needle == d["district"].lower() or needle == d["id"]:
            scored.append((0, d))
        elif ranks and min(ranks) == 0:
            scored.append((1, d))
        elif needle in d["district"].lower() and len(needle) >= 5:
            first = d["district"].lower().split()[0]
            # "puri" must not stem-hit Purulia; "purba" may hit Purba Medinipur.
            if not (first.startswith(needle) and len(first) - len(needle) >= 2):
                scored.append((2, d))
        elif any(needle == a.lower() or fold(needle) == fold(a) for a in d["aliases"] if a):
            scored.append((1, d))
        elif any(len(a) >= 5 and (needle in a or a in needle) and abs(len(a) - len(needle)) <= 2 for a in d["aliases"] if a):
            scored.append((3, d))
        elif any(close_enough(needle, n) for n in names if n):
            scored.append((4 + int((1 - ratio(needle, d["district"])) * 10), d))
        elif len(needle) >= 6 and needle in blob and not is_state_name(needle):
            scored.append((8, d))
    scored.sort(key=lambda x: (x[0], x[1]["label"]))
    return [d for _, d in scored[:limit]]


def all_states() -> list[str]:
    return sorted({d["state"] for d in all_districts()})


_STATE_ALIASES = {
    "wb": "West Bengal",
    "bengal": "West Bengal",
    "orissa": "Odisha",
    "tn": "Tamil Nadu",
    "up": "Uttar Pradesh",
    "mp": "Madhya Pradesh",
    "hp": "Himachal Pradesh",
    "uk": "Uttarakhand",
    "ap": "Andhra Pradesh",
    "j&k": "Jammu and Kashmir",
    "a&n": "Andaman and Nicobar",
    "andaman": "Andaman and Nicobar",
}


def is_state_name(q: str) -> bool:
    """True when the whole string is a state / UT, not a district."""
    n = (q or "").strip().lower()
    if not n:
        return False
    if n in {s.lower() for s in all_states()}:
        return True
    if n in _STATE_ALIASES:
        return True
    if n in {"west bengal", "tamil nadu", "uttar pradesh", "madhya pradesh",
             "andhra pradesh", "himachal pradesh", "jammu and kashmir",
             "andaman and nicobar", "dadra and nagar haveli"}:
        return True
    return False


def districts_in_state(state: str) -> list[dict]:
    needle = (state or "").strip().lower()
    if not needle:
        return list(all_districts())
    aliases = {
        "wb": "west bengal",
        "bengal": "west bengal",
        "up": "uttar pradesh",
        "tn": "tamil nadu",
        "ap": "andhra pradesh",
        "mp": "madhya pradesh",
        "hp": "himachal pradesh",
        "uk": "uttarakhand",
        "j&k": "jammu and kashmir",
    }
    needle = aliases.get(needle, needle)
    out = [d for d in all_districts() if needle in d["state"].lower() or d["state"].lower() in needle]
    return out or list(all_districts())


def extract_places(text: str) -> list[str]:
    """All district names mentioned, longest match first. Fuzzy on tokens (Puruliya)."""
    from app.data.fuzzy import close_enough, tokens

    blob = (text or "").lower()
    found: dict[str, int] = {}
    for d in all_districts():
        names = [d["district"], *[a for a in d["aliases"] if a]]
        for n in names:
            key = n.strip().lower()
            if len(key) < 4:
                continue
            if re.search(rf"(?<![a-z]){re.escape(key)}(?![a-z])", blob):
                found[d["district"]] = max(found.get(d["district"], 0), len(key))
    if not found:
        for tok in tokens(text or ""):
            for d in all_districts():
                names = [d["district"], *d["aliases"]]
                if any(close_enough(tok, n) for n in names if n):
                    found[d["district"]] = max(found.get(d["district"], 0), len(tok))
    return [name for name, _ in sorted(found.items(), key=lambda x: -x[1])]


def extract_place(text: str) -> str | None:
    """Longest district / alias mentioned in free text (e.g. Haldia, Darjeeling)."""
    hits = extract_places(text)
    return hits[0] if hits else None


def match_states(text: str) -> list[str]:
    """Every gazetteer state whose name or alias appears in the text."""
    blob = (text or "").lower()
    found: list[str] = []
    seen: set[str] = set()
    for s in all_states():
        if s.lower() in blob and s not in seen:
            seen.add(s)
            found.append(s)
    for alias, full in {
        "west bengal": "West Bengal",
        "wb ": "West Bengal",
        "odisha": "Odisha",
        "orissa": "Odisha",
        "tamil nadu": "Tamil Nadu",
        "uttar pradesh": "Uttar Pradesh",
        "madhya pradesh": "Madhya Pradesh",
        "andhra": "Andhra Pradesh",
        "maharashtra": "Maharashtra",
        "karnataka": "Karnataka",
        "kerala": "Kerala",
        "gujarat": "Gujarat",
        "rajasthan": "Rajasthan",
        "bihar": "Bihar",
        "jharkhand": "Jharkhand",
        "assam": "Assam",
        "punjab": "Punjab",
        "haryana": "Haryana",
        "delhi": "Delhi",
        "telangana": "Telangana",
        "chhattisgarh": "Chhattisgarh",
        "পশ্চিমবঙ্গ": "West Bengal",
        "पश्चिम बंगाल": "West Bengal",
        "ओडिशा": "Odisha",
        "राजस्थान": "Rajasthan",
        "महाराष्ट्र": "Maharashtra",
        "केरल": "Kerala",
        "पंजाब": "Punjab",
    }.items():
        if alias in blob and full not in seen:
            seen.add(full)
            found.append(full)
    return found


def match_state(text: str) -> str | None:
    blob = (text or "").lower()
    for s in all_states():
        if s.lower() in blob:
            return s
    for alias, full in {
        "west bengal": "West Bengal",
        "wb ": "West Bengal",
        " gangetic": "West Bengal",
        "odisha": "Odisha",
        "orissa": "Odisha",
        "tamil nadu": "Tamil Nadu",
        "uttar pradesh": "Uttar Pradesh",
        "madhya pradesh": "Madhya Pradesh",
        "andhra": "Andhra Pradesh",
        "maharashtra": "Maharashtra",
        "karnataka": "Karnataka",
        "kerala": "Kerala",
        "gujarat": "Gujarat",
        "rajasthan": "Rajasthan",
        "bihar": "Bihar",
        "jharkhand": "Jharkhand",
        "assam": "Assam",
        "punjab": "Punjab",
        "haryana": "Haryana",
        "delhi": "Delhi",
        "telangana": "Telangana",
        "chhattisgarh": "Chhattisgarh",
        "পশ্চিমবঙ্গ": "West Bengal",
        "পশ্চিম বঙ্গ": "West Bengal",
        "पश्चिम बंगाल": "West Bengal",
        "ओडिशा": "Odisha",
        "उड़ीसा": "Odisha",
        "राजस्थान": "Rajasthan",
        "महाराष्ट्र": "Maharashtra",
        "बिहार": "Bihar",
        "অসম": "Assam",
    }.items():
        if alias in blob:
            return full
    return None


def nearest(lat: float, lon: float) -> dict:
    best = None
    best_d = 1e18
    for d in all_districts():
        dd = (d["lat"] - lat) ** 2 + (d["lon"] - lon) ** 2
        if dd < best_d:
            best_d = dd
            best = d
    return best or default_district()

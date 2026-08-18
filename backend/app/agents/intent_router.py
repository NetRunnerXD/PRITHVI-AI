from __future__ import annotations

import re

from app.data.india_districts import extract_place, match_state
from app.science.vernacular import observe_speech

_INTENT_WORDS = {
    "rank": [
        "which district", "which districts", "list them", "list the district",
        "most likely", "more likely", "rank", "ranking", "worst hit",
        "prone", "highest flood", "most flood", "কোন কোন জেলা", "कौन से जिले",
    ],
    "list": [
        "all district", "all districts", "all cities", "all city", "list all",
        "list district", "list state", "every district", "gazetteer",
    ],
    "irrigation": [
        "irrigat", "sech", "সেচ", "सिंचाई", "sinchai", "water the", "should i water",
        "field water", "पानी देना",
    ],
    "rain": [
        "rain", "precip", "বৃষ্টি", "बारिश", "वर्षा", "monsoon", "বর্ষা",
        "shower", "downpour",
    ],
    "flood": ["flood", "বন্যা", "बाढ़", "inundat", "waterlog", "জলাবদ্ধ", "নদী আসছে", "নদী ভাঙ"],
    "seismic": ["earthquake", "quake", "seismic", "भूकंप", "ভূমিকম্প", "aftershock"],
    "tsunami": ["tsunami", "সুনামি", "सुनामी", "itews"],
    "marine": ["marine", "wave height", "swell", "sea state", "समुद्री", "সমুদ্র তরঙ্গ"],
    "drought": ["drought", "খরা", "सूखा", "dry spell", "deficit"],
    "heat": ["heat", "গরম", "गर्मी", "heatwave", "তাপদাহ", "hot day"],
    "aqi": ["aqi", "air quality", "pollution", "smog", "pm2", "प्रदूषण", "দূষণ"],
    "price": ["mandi", "price", "bhav", "भाव", "দাম", "মূল্য", "rate", "agmark"],
    "compare": ["compare", "versus", " vs ", "तुलना", "তুলনা", "difference between"],
    "outlook": ["7 day", "seven day", "week", "outlook", "আগামী সপ্তাহ", "अगला सप्ताह", "water balance"],
    "crop": ["crop", "ফসল", "फसल", "rice", "ধান", "wheat", "vegetab"],
}


def extract_state(text: str) -> str | None:
    return match_state(text or "")


def mentioned_place(text: str) -> str | None:
    return extract_place(text or "")


def extract_metric(text: str) -> str:
    t = (text or "").lower()
    if any(w in t for w in ("drought", "খরা", "सूखा", "dry")):
        return "drought"
    if any(w in t for w in ("heat", "গরম", "गर्मी")):
        return "heat"
    if any(w in t for w in ("irrigat", "সেচ", "सिंचाई")):
        return "irrigation"
    if any(w in t for w in ("price", "mandi", "দাম", "भाव")):
        return "price"
    if any(w in t for w in ("rain", "বৃষ্টি", "बारिश")) and "flood" not in t:
        return "rain"
    return "flood"


def classify(text: str) -> str:
    t = (text or "").lower()
    tags = set(observe_speech(text).get("tags") or [])
    hits: dict[str, int] = {}
    for intent, words in _INTENT_WORDS.items():
        hits[intent] = sum(1 for w in words if w in t)
    if hits.get("rank") or (
        hits.get("flood") and any(w in t for w in ("which", "list", "district", "জেলা", "जिला"))
    ):
        return "rank"
    if hits.get("list"):
        return "list"
    if tags & {"river_rise", "flood", "waterlog", "tide"} and not hits.get("irrigation"):
        hits["flood"] = hits.get("flood", 0) + 1
    if tags & {"irrigate"}:
        hits["irrigation"] = hits.get("irrigation", 0) + 1
    if tags & {"dry_spell"}:
        hits["drought"] = hits.get("drought", 0) + 1
    if tags & {"heat"}:
        hits["heat"] = hits.get("heat", 0) + 1
    best = max(hits, key=hits.get)
    if hits[best] == 0:
        return "general"
    if hits["compare"]:
        return "compare"
    if hits["irrigation"] and hits["rain"]:
        return "irrigation"
    return best


def required_tools(intent: str) -> list[str]:
    packs = {
        "rank": ["list_districts", "rank_districts"],
        "list": ["list_states", "list_districts"],
        "irrigation": ["get_nowcast", "get_weather_forecast", "get_soil_moisture", "get_prescriptions", "get_water_balance", "get_science_pack"],
        "rain": ["get_nowcast", "get_weather_forecast", "get_7day_outlook", "get_science_pack"],
        "flood": ["get_imd_warnings", "get_nowcast", "get_flood_outlook", "get_hazard_watch", "rank_districts", "get_science_pack"],
        "seismic": ["get_hazard_watch"],
        "tsunami": ["get_hazard_watch"],
        "marine": ["get_hazard_watch", "get_weather_forecast"],
        "drought": ["get_weather_forecast", "get_water_balance"],
        "heat": ["get_weather_forecast"],
        "aqi": ["get_air_quality"],
        "price": ["get_mandi_prices", "get_state_mandi"],
        "compare": ["compare_districts"],
        "outlook": ["get_nowcast", "get_7day_outlook", "get_water_balance", "get_science_pack"],
        "crop": ["retrieve_playbook", "get_mandi_prices", "get_science_pack"],
        "general": ["get_nowcast", "get_weather_forecast", "get_imd_warnings", "get_hazard_watch", "get_science_pack"],
    }
    return list(packs.get(intent, packs["general"]))


def looks_like_place(text: str) -> bool | str:
    m = re.search(r"\b(?:in|at|near|vs|versus)\s+([A-Z][a-zA-Z]+(?:\s+[A-Z][a-zA-Z]+)?)", text or "")
    if m:
        return m.group(1)
    return False

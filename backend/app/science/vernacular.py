"""Indic climate speech as a sensor. Tags categories — never invents millimetres."""

from __future__ import annotations

from typing import Any

# phrase → physical category. Longer phrases first.
_LEXICON: list[tuple[str, str]] = [
    ("কালবৈশাখী", "squall"),
    ("kal baisakhi", "squall"),
    ("নদী আসছে", "river_rise"),
    ("নদী ভাঙ", "river_rise"),
    ("জোয়ার", "tide"),
    ("জোয়ারভাটা", "tide"),
    ("জলাবদ্ধ", "waterlog"),
    ("waterlog", "waterlog"),
    ("ঝমাঝম", "heavy_rain"),
    ("झमाझम", "heavy_rain"),
    ("রिमझिम", "drizzle"),
    ("রिमझिम", "drizzle"),
    ("গুঁড়ি গুঁড়ি", "drizzle"),
    ("फुहार", "drizzle"),
    ("বন্যা", "flood"),
    ("बाढ़", "flood"),
    ("খরা", "dry_spell"),
    ("सूखा", "dry_spell"),
    ("তাপদাহ", "heat"),
    ("लू", "heat"),
    ("সেচ", "irrigate"),
    ("सिंचाई", "irrigate"),
    ("মাটি শক্ত", "hard_soil"),
    ("मिट्टी सख्त", "hard_soil"),
    ("মাটি ভেজা", "wet_soil"),
    ("कीचड़", "wet_soil"),
    ("downpour", "heavy_rain"),
    ("the river is coming", "river_rise"),
    ("বৰদৈচিলা", "squall"),
    ("bordoisila", "squall"),
    ("କାଳ ବୈଶାଖୀ", "squall"),
    ("kala baisakhi", "squall"),
    ("norwester", "squall"),
    ("nor'wester", "squall"),
    ("ঘাট", "tide"),
    ("ghat", "tide"),
]


def observe_speech(text: str) -> dict[str, Any]:
    blob = (text or "").lower()
    raw = text or ""
    tags: list[str] = []
    hits: list[str] = []
    for phrase, tag in _LEXICON:
        if phrase.lower() in blob or phrase in raw:
            if tag not in tags:
                tags.append(tag)
                hits.append(phrase)
    return {
        "tags": tags,
        "hits": hits,
        "method": "vernacular lexicon v1",
        "note": "Speech updates category and timing only. Millimetres stay on tools.",
    }


def name_state(f: dict[str, Any], hy: dict[str, Any]) -> dict[str, Any]:
    """Invert: what a local speaker would likely call today's state."""
    rain = float(f.get("precip_today_mm") or 0)
    rain3 = float(f.get("precip_3d_mm") or 0)
    tmax = (f.get("temp_max") or [30])[0]
    soil = float(f.get("soil_m3m3") or 0.25)
    en, hi, bn = "fair", "सामान्य", "সাধারণ"
    tag = "fair"
    if rain3 >= 40 or hy.get("flip") == "runoff":
        tag, en, hi, bn = "flood_watch", "the river / fields are coming up", "बाढ़ जैसे हालात", "নদী/জমি ভরে আসছে"
    elif rain >= 15 or rain3 >= 25:
        tag, en, hi, bn = "heavy_rain", "heavy rain / downpour", "झमाझम बारिश", "ঝমাঝম বৃষ্টি"
    elif 0 < rain < 4:
        tag, en, hi, bn = "drizzle", "light drizzle", "रिमझिम फुहार", "গুঁড়ি গুঁড়ি বৃষ্টি"
    elif tmax >= 38:
        tag, en, hi, bn = "heat", "heatwave day", "लू / गर्मी", "তাপদাহ"
    elif soil <= 0.18 and rain3 < 5:
        tag, en, hi, bn = "dry_spell", "dry spell", "सूखा पड़ रहा", "খরার গন্ধ"
    elif soil >= 0.34:
        tag, en, hi, bn = "wet_soil", "fields are sodden", "कीचड़ / गीली मिट्टी", "মাটি ভেজা / কাদা"
    return {
        "tag": tag,
        "en": en,
        "hi": hi,
        "bn": bn,
        "method": "physical-to-vernacular invert v1",
    }

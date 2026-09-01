"""IMD official REST + public CAP feed.

Official JSON at api.imd.gov.in requires IP whitelist (or a future API key).
CAP RSS is public and is the live India-official warning source on day one.
"""

from __future__ import annotations

import html
import re
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from typing import Any

from app import cache
from app.config import get_settings
from app.providers.http import client

CAP_RSS = "https://cap-sources.s3.amazonaws.com/in-imd-en/rss.xml"


async def official_get(path: str, params: dict | None = None) -> tuple[dict | list | None, str]:
    """Try official IMD REST. Returns (payload, status) where status is ok|unauthorized|error."""
    settings = get_settings()
    headers = {}
    if settings.imd_api_key:
        headers["Authorization"] = f"Bearer {settings.imd_api_key}"
        headers["X-API-Key"] = settings.imd_api_key
    url = f"{settings.imd_api_base.rstrip('/')}/{path.lstrip('/')}"
    try:
        r = await client().get(url, params=params, headers=headers)
        if r.status_code == 401:
            return None, "unauthorized"
        r.raise_for_status()
        return r.json(), "ok"
    except Exception:
        return None, "error"


async def city_forecast(station_id: str) -> tuple[Any, str]:
    return await official_get("cityforecast", {"id": station_id})


async def district_rainfall(district_id: str) -> tuple[Any, str]:
    return await official_get("districtrainfall", {"id": district_id})


async def district_warnings(district_id: str | None = None) -> tuple[Any, str]:
    params = {"id": district_id} if district_id else None
    return await official_get("districtwarning", params)


async def basin_qpf() -> tuple[Any, str]:
    return await official_get("basinqpf")


async def cap_alerts(force: bool = False) -> list[dict[str, Any]]:
    if not force:
        hit = cache.get("imd:cap")
        if hit is not None:
            return hit
    r = await client().get(CAP_RSS)
    r.raise_for_status()
    root = ET.fromstring(r.text)
    items = []
    for item in root.findall("./channel/item"):
        title = (item.findtext("title") or "").strip()
        desc = (item.findtext("description") or "").strip()
        link = (item.findtext("link") or "").strip()
        pub = (item.findtext("pubDate") or "").strip()
        items.append(
            {
                "id": (item.findtext("guid") or link or title)[:80],
                "title": title,
                "body": desc,
                "link": link,
                "published": pub,
                "source": "imd-cap",
            }
        )
    cache.set("imd:cap", items, 15 * 60)
    return items


def alerts_for_location(alerts: list[dict], location) -> list[dict]:
    """Filter CAP items that mention the state, district, or IMD subdivision."""
    keys = {
        location.state.lower(),
        location.district.lower(),
        (location.imd_subdivision or "").lower(),
        "gangetic west bengal" if "west bengal" in location.state.lower() else "",
        "west bengal" if "bengal" in location.state.lower() else "",
    }
    keys.discard("")
    matched = []
    for a in alerts:
        blob = f"{a['title']} {a['body']}".lower()
        if any(k and k in blob for k in keys):
            matched.append(a)
    return matched


def is_national_severe(title: str, body: str = "") -> bool:
    t = f"{title} {body}".lower()
    return any(
        x in t
        for x in (
            "extreme",
            "red alert",
            "orange",
            "very heavy",
            "extremely heavy",
            "cyclone",
            "cyclonic storm",
            "depression",
            "severe thunderstorm",
            "cloudburst",
            "flash flood",
            "heat wave",
            "heatwave",
            "cold wave",
            "drought",
            "tsunami warning",
        )
    )


def national_severe(alerts: list[dict]) -> list[dict]:
    """IMD CAP items that are severe anywhere in India (not just the pin)."""
    out = []
    seen: set[str] = set()
    for a in alerts:
        title = a.get("title") or ""
        if not is_national_severe(title, a.get("body") or ""):
            continue
        key = title.lower()[:96]
        if key in seen:
            continue
        seen.add(key)
        out.append(a)
        if len(out) >= 10:
            break
    return out


INDIAN_REGIONS = (
    "Andaman and Nicobar", "Andhra Pradesh", "Arunachal Pradesh", "Assam", "Bihar",
    "Chandigarh", "Chhattisgarh", "Dadra and Nagar Haveli", "Daman and Diu", "Delhi",
    "Goa", "Gujarat", "Haryana", "Himachal Pradesh", "Jammu and Kashmir", "Jharkhand",
    "Karnataka", "Kerala", "Ladakh", "Lakshadweep", "Madhya Pradesh", "Maharashtra",
    "Manipur", "Meghalaya", "Mizoram", "Nagaland", "Odisha", "Puducherry", "Punjab",
    "Rajasthan", "Sikkim", "Tamil Nadu", "Telangana", "Tripura", "Uttar Pradesh",
    "Uttarakhand", "West Bengal", "Konkan", "Vidarbha", "Marathwada", "Madhya Maharashtra",
    "Saurashtra", "Kutch", "Rayalaseema", "Coastal Andhra", "North Interior Karnataka",
    "South Interior Karnataka", "Coastal Karnataka", "Malabar", "Gangetic West Bengal",
    "Sub-Himalayan West Bengal"
)


def extract_region_hint(title: str, body: str = "") -> str:
    blob = f"{title} {body}".lower()
    for reg in INDIAN_REGIONS:
        if reg.lower() in blob:
            return reg
    return ""


def severity_from_title(title: str) -> str:
    t = title.lower()
    if "extreme" in t or "red" in t:
        return "extreme"
    if "very heavy" in t or "severe" in t or "warning" in t:
        return "warning"
    if "heavy" in t or "alert" in t:
        return "alert"
    return "watch"


def humanize_cap_title(title: str, body: str = "", place: str = "") -> str:
    """Turn stacked IMD CAP phrases into one readable warning line."""
    raw = (title or "").strip()
    low = f"{raw} {body or ''}".lower()
    where = f" — {place}" if place else ""
    if "cyclone" in low or "depression" in low:
        kind = "Cyclone / depression bulletin"
    elif "severe thunderstorm" in low or "squall" in low:
        kind = "Severe thunderstorm warning"
    elif "thunderstorm" in low or "lightning" in low:
        kind = "Thunderstorm & lightning warning"
    elif "heat" in low:
        kind = "Heatwave warning"
    elif "flood" in low:
        kind = "Flood warning"
    elif "extremely heavy" in low or ("extreme" in low and "rain" in low):
        kind = "Extremely heavy rainfall warning"
    elif "very heavy" in low:
        kind = "Very heavy rainfall warning"
    elif "heavy" in low and "rain" in low:
        kind = "Heavy rainfall warning"
    elif "rain" in low:
        kind = "Rainfall warning"
    else:
        cleaned = " ".join(raw.split())
        cleaned = re.sub(r"^(imd\s*(alert|bulletin|warning)?\s*[:\-–—]\s*)+", "", cleaned, flags=re.I).strip()
        if len(cleaned) > 72:
            cleaned = cleaned[:69] + "…"
        return f"{cleaned}{where}" if cleaned else f"IMD weather bulletin{where}"
    return f"{kind}{where}"


_STACKED_RAIN = re.compile(
    r"heavy\s+to\s+very\s+heavy|extremely heavy rainfall at|heavy to very heavy with",
    re.I,
)


def clean_cap_body(body: str, *, title: str = "", raw_title: str = "") -> str:
    """Drop stacked IMD intensity phrases; keep one useful sentence."""
    text = re.sub(r"<[^>]+>", " ", body or "")
    text = html.unescape(text)
    text = " ".join(text.split())
    for drop in (raw_title, title):
        if drop and len(drop) > 5:
            text = re.sub(re.escape(drop), " ", text, flags=re.I)
    keep: list[str] = []
    for part in re.split(r"(?<=[.!?])\s+", text):
        chunk = part.strip(" .")
        if not chunk:
            continue
        if _STACKED_RAIN.search(chunk):
            continue
        low = chunk.lower()
        if re.fullmatch(r"(heavy|very heavy|extremely heavy)(\s+(to|with)\s+(very heavy|extremely heavy))*(\s+rainfall)?", low):
            continue
        if low in {"warning", "alert", "watch", "imd alert", "nil", "none"}:
            continue
        keep.append(chunk)
    out = ". ".join(keep).strip(" .")
    if len(out) > 220:
        out = out[:217].rstrip() + "…"
    return out


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


"""NDMA SACHET CAP RSS. District/state alerts — timing prior only, never mm."""

from __future__ import annotations

import asyncio
import xml.etree.ElementTree as ET
from typing import Any

from app import cache
from app.providers.http import client

IN_RSS = "https://sachet.ndma.gov.in/cap_public_website/rss/rss_india.xml"

# NDMA public RSS slugs. Unknown slugs 404 and are skipped.
STATE_SLUGS: dict[str, str] = {
    "andaman and nicobar": "andamanandnicobar",
    "andhra pradesh": "andhrapradesh",
    "arunachal pradesh": "arunachalpradesh",
    "assam": "assam",
    "bihar": "bihar",
    "chandigarh": "chandigarh",
    "chhattisgarh": "chhattisgarh",
    "delhi": "delhi",
    "goa": "goa",
    "gujarat": "gujarat",
    "haryana": "haryana",
    "himachal pradesh": "himachalpradesh",
    "jammu and kashmir": "jammuandkashmir",
    "jharkhand": "jharkhand",
    "karnataka": "karnataka",
    "kerala": "kerala",
    "ladakh": "ladakh",
    "lakshadweep": "lakshadweep",
    "madhya pradesh": "madhyapradesh",
    "maharashtra": "maharashtra",
    "manipur": "manipur",
    "meghalaya": "meghalaya",
    "mizoram": "mizoram",
    "nagaland": "nagaland",
    "odisha": "odisha",
    "puducherry": "puducherry",
    "punjab": "punjab",
    "rajasthan": "rajasthan",
    "sikkim": "sikkim",
    "tamil nadu": "tamilnadu",
    "telangana": "telangana",
    "tripura": "tripura",
    "uttar pradesh": "uttarpradesh",
    "uttarakhand": "uttarakhand",
    "west bengal": "westbengal",
}


def _rss_url(slug: str) -> str:
    return f"https://sachet.ndma.gov.in/cap_public_website/rss/rss_{slug}.xml"


def _parse_rss(text: str) -> list[dict[str, Any]]:
    root = ET.fromstring(text)
    items: list[dict[str, Any]] = []
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
                "url": link,
                "published": pub,
                "source": "sachet-ndma",
            }
        )
    return items


async def _fetch_one(url: str, key: str) -> list[dict[str, Any]]:
    hit = cache.get(key)
    if hit is not None:
        return hit if isinstance(hit, list) else []
    try:
        r = await client().get(url, timeout=12.0)
        if r.status_code >= 400:
            cache.set(key, [], 10 * 60)
            return []
        items = _parse_rss(r.text)
        cache.set(key, items, 10 * 60)
        return items
    except Exception:
        cache.set(key, [], 5 * 60)
        return []


async def alerts(state: str | None = None) -> tuple[list[dict[str, Any]], str]:
    """India RSS + pinned-state RSS + cached remaining state feeds."""
    key_all = "sachet:all-india-v2"
    hit = cache.get(key_all)
    if hit is not None:
        return hit, "ok" if hit else "empty"

    urls = [("in", IN_RSS)]
    pin_slug = STATE_SLUGS.get((state or "").lower().strip())
    if pin_slug:
        urls.append((pin_slug, _rss_url(pin_slug)))
    for st, slug in STATE_SLUGS.items():
        if slug == pin_slug:
            continue
        urls.append((slug, _rss_url(slug)))

    rows = await asyncio.gather(*[_fetch_one(u, f"sachet:{k}") for k, u in urls])
    seen: set[str] = set()
    out: list[dict[str, Any]] = []
    for items in rows:
        for it in items:
            kid = str(it.get("id") or it.get("title") or "")[:80]
            if kid in seen:
                continue
            seen.add(kid)
            out.append(it)
    cache.set(key_all, out, 10 * 60)
    return out, "ok" if out else "empty"

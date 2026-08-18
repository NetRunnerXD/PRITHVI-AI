"""NDMA SACHET CAP RSS. District/state alerts — timing prior only, never mm."""

from __future__ import annotations

import xml.etree.ElementTree as ET
from typing import Any

from app import cache
from app.providers.http import client

WB_RSS = "https://sachet.ndma.gov.in/cap_public_website/rss/rss_westbengal.xml"
IN_RSS = "https://sachet.ndma.gov.in/cap_public_website/rss/rss_india.xml"


async def alerts(state: str | None = None) -> tuple[list[dict[str, Any]], str]:
    key = f"sachet:{(state or 'in').lower()}"
    hit = cache.get(key)
    if hit is not None:
        return hit, "ok"
    url = WB_RSS if (state or "").lower() in {"west bengal", "wb"} else IN_RSS
    try:
        r = await client().get(url)
        r.raise_for_status()
        root = ET.fromstring(r.text)
        items: list[dict[str, Any]] = []
        for item in root.findall("./channel/item"):
            title = (item.findtext("title") or "").strip()
            desc = (item.findtext("description") or "").strip()
            link = (item.findtext("link") or "").strip()
            items.append(
                {
                    "id": (item.findtext("guid") or link or title)[:80],
                    "title": title,
                    "body": desc,
                    "link": link,
                    "source": "sachet-ndma",
                }
            )
        cache.set(key, items, 15 * 60)
        return items, "ok"
    except Exception:
        return [], "error"

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


FRESH_S = 10 * 60
STALE_S = 6 * 3600


async def _download(url: str) -> list[dict[str, Any]]:
    r = await client().get(url, timeout=8.0)
    if r.status_code >= 400:
        return []
    return _parse_rss(r.text)


async def _fetch_one(url: str, key: str) -> list[dict[str, Any]]:
    """Cached feed. The download runs as a shielded shared task: a caller's timeout
    (snapshot gives Sachet ~2 s) no longer cancels the fetch, so the next request is warm
    instead of starting over (previously 36 feeds were re-fetched and cancelled each time)."""
    try:
        got = await asyncio.shield(cache.aget(key, lambda: _download(url), ttl_s=FRESH_S, swr_s=STALE_S))
    except asyncio.CancelledError:
        raise
    except Exception:
        cache.set(key, [], 5 * 60)
        return []
    return got if isinstance(got, list) else []


async def alerts(state: str | None = None) -> tuple[list[dict[str, Any]], str]:
    """All-India RSS (which already carries every state's CAP alerts) + the pinned state's
    feed. The other 34 state feeds are no longer fetched on every request."""
    pin_slug = STATE_SLUGS.get((state or "").lower().strip())
    key_all = f"sachet:merged:{pin_slug or 'in'}"
    hit = cache.get(key_all)
    if hit is not None:
        return hit, "ok" if hit else "empty"
    urls = [("in", IN_RSS)]
    if pin_slug:
        urls.append((pin_slug, _rss_url(pin_slug)))
    rows = list(await asyncio.gather(*[_fetch_one(u, f"sachet:{k}") for k, u in urls]))
    # The India feed is capped at 100 items: also merge any state feeds that the background
    # prefetcher already warmed (cache only — no network here).
    for slug in STATE_SLUGS.values():
        if slug != pin_slug:
            warm = cache.peek(f"sachet:{slug}")
            if isinstance(warm, list) and warm:
                rows.append(warm)
    seen: set[str] = set()
    out: list[dict[str, Any]] = []
    for items in rows:
        for it in items:
            kid = str(it.get("id") or it.get("title") or "")[:80]
            if kid in seen:
                continue
            seen.add(kid)
            out.append(it)
    out = await enrich_cap(out)
    cache.set(key_all, out, 5 * 60)
    if out:
        _LAST["rows"] = out
    return out, "ok" if out else "empty"


_LAST: dict[str, list[dict[str, Any]]] = {"rows": []}
_WARM: dict[str, asyncio.Task] = {}


async def alerts_fast(state: str | None = None, budget_s: float = 2.0) -> tuple[list[dict[str, Any]], str]:
    """`alerts()` within a time budget. On a slow link the pinned state's feed + CAP files can
    take longer than the dashboard budget; instead of returning nothing (which dropped every
    India-wide alert for that pin), keep the fetch running in the background and serve the
    last merged All-India rows (the per-pin locality filter runs downstream)."""
    key = (state or "").lower().strip()
    task = _WARM.get(key)
    if task is None or task.done():
        task = asyncio.ensure_future(alerts(state))
        _WARM[key] = task
    try:
        return await asyncio.wait_for(asyncio.shield(task), timeout=budget_s)
    except asyncio.TimeoutError:
        rows = _LAST["rows"] or cache.peek("sachet:in") or []
        return list(rows), "partial" if rows else "timeout"


_CAP_NS = "{urn:oasis:names:tc:emergency:cap:1.2}"


def parse_cap(text: str) -> dict[str, Any]:
    """CAP 1.2 timing (ISO with +05:30 offset as issued by SDMA/IMD) and area."""
    try:
        root = ET.fromstring(text)
    except ET.ParseError:
        return {}
    info = root.find(f"{_CAP_NS}info")
    if info is None:
        return {}

    def t(el, tag: str) -> str | None:
        v = (el.findtext(f"{_CAP_NS}{tag}") or "").strip() if el is not None else ""
        return v or None

    area = info.find(f"{_CAP_NS}area")
    return {
        "sent": t(root, "sent"),
        "msg_type": t(root, "msgType"),
        "effective": t(info, "effective"),
        "onset": t(info, "onset"),
        "expires": t(info, "expires"),
        "event": t(info, "event"),
        "cap_severity": t(info, "severity"),
        "urgency": t(info, "urgency"),
        "certainty": t(info, "certainty"),
        "headline": t(info, "headline"),
        "area_desc": t(area, "areaDesc"),
    }


async def _cap_one(item: dict[str, Any]) -> dict[str, Any]:
    url = item.get("link") or ""
    if "FetchXMLFile" not in url:
        return {}

    async def dl() -> dict[str, Any]:
        r = await client().get(url, timeout=8.0)
        return parse_cap(r.text) if r.status_code < 400 else {}

    try:
        # CAP messages are immutable: cache per identifier for a day.
        return await asyncio.shield(cache.aget(f"sachet:cap:{item.get('id')}", dl, ttl_s=86400, swr_s=86400))
    except asyncio.CancelledError:
        raise
    except Exception:
        return {}


async def enrich_cap(items: list[dict[str, Any]], limit: int = 120, concurrency: int = 8) -> list[dict[str, Any]]:
    """Attach CAP onset/expires so alert windows are real, not guessed from pubDate.
    Downloads are shielded and cached, so a caller timeout leaves them warming."""
    sem = asyncio.Semaphore(concurrency)

    async def one(it: dict[str, Any]) -> dict[str, Any]:
        async with sem:
            cap = await _cap_one(it)
        if not cap:
            return it
        return {**it, **{k: v for k, v in cap.items() if v}, "body": it.get("body") or cap.get("headline") or ""}

    head = await asyncio.gather(*(one(it) for it in items[:limit]), return_exceptions=True)
    return [h if isinstance(h, dict) else items[i] for i, h in enumerate(head)] + items[limit:]


async def warm_all_states(concurrency: int = 4) -> int:
    """Background job: refresh every state feed slowly (4 at a time). Not on the request path."""
    sem = asyncio.Semaphore(concurrency)
    n = 0

    async def one(slug: str) -> None:
        nonlocal n
        async with sem:
            items = await _fetch_one(_rss_url(slug), f"sachet:{slug}")
            n += 1 if items else 0

    await asyncio.gather(*(one(s) for s in STATE_SLUGS.values()), return_exceptions=True)
    return n

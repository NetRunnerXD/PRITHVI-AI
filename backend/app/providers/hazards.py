"""Seismic + tsunami: Open-Meteo does not publish these.

India-first: INCOIS ITEWS JSON catalog (past90days) + USGS FDSN for the
India–Indian Ocean box (NCS has no stable public JSON). IMD CAP remains weather.
ITEWS TLS often lacks a public CA — verify is disabled only for that host.
"""

from __future__ import annotations

import asyncio
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from math import atan2, cos, radians, sin, sqrt
from typing import Any

import httpx

from app import cache
from app.providers.http import client

USGS = "https://earthquake.usgs.gov/fdsnws/event/1/query"
INCOIS_CATALOG = "https://tsunami.incois.gov.in/itews/DSSProducts/OPR/past90days.json"
INCOIS_FEEDS = (
    "https://tsunami.incois.gov.in/itews/DSS/eqrss.xml",
    "https://tsunami.incois.gov.in/TEWS/eqrss.xml",
)


def _km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371.0
    p1, p2 = radians(lat1), radians(lat2)
    dp, dl = radians(lat2 - lat1), radians(lon2 - lon1)
    a = sin(dp / 2) ** 2 + cos(p1) * cos(p2) * sin(dl / 2) ** 2
    return 2 * r * atan2(sqrt(a), sqrt(max(0.0, 1 - a)))


async def recent_quakes(lat: float, lon: float, limit: int = 8) -> tuple[list[dict[str, Any]], str]:
    hit = cache.get("usgs:india")
    if hit is None:
        params = {
            "format": "geojson",
            "minlatitude": 5,
            "maxlatitude": 38,
            "minlongitude": 60,
            "maxlongitude": 100,
            "orderby": "time",
            "limit": 20,
            "starttime": (datetime.now(timezone.utc) - timedelta(days=7)).strftime("%Y-%m-%d"),
        }
        try:
            r = await client().get(USGS, params=params, timeout=8.0)
            r.raise_for_status()
            hit = r.json()
            cache.set("usgs:india", hit, 10 * 60)
        except Exception:
            return [], "error"
    feats = hit.get("features") or []
    out = []
    for f in feats:
        props = f.get("properties") or {}
        coords = ((f.get("geometry") or {}).get("coordinates")) or [None, None, None]
        elon, elat, depth = (coords + [None, None, None])[:3]
        dist = None
        if elat is not None and elon is not None:
            dist = round(_km(lat, lon, float(elat), float(elon)), 0)
        mag = props.get("mag")
        ms = props.get("time")
        time_iso = None
        if isinstance(ms, (int, float)):
            time_iso = datetime.fromtimestamp(ms / 1000, tz=timezone.utc).isoformat()
        out.append(
            {
                "id": f.get("id"),
                "mag": mag,
                "place": props.get("place"),
                "time": ms,
                "time_iso": time_iso,
                "url": props.get("url"),
                "lat": elat,
                "lon": elon,
                "depth_km": depth,
                "distance_km": dist,
                "source": "USGS FDSN (India–Indian Ocean box; NCS has no public JSON)",
                "tsunami_flag": bool(props.get("tsunami")),
            }
        )
    out.sort(key=lambda x: (x.get("distance_km") is None, x.get("distance_km") or 1e9))
    return out[:limit], "ok"


def _threat(text: str) -> bool:
    low = (text or "").lower()
    if any(x in low for x in ("does not exist", "no tsunami", "no threat", "threat does not", "all clear")):
        return False
    return any(x in low for x in ("tsunami threat", "warning", "watch", "alert", "inundation"))


def parse_incois_catalog(data: dict, details: dict[str, dict] | None = None) -> list[dict[str, Any]]:
    details = details or {}
    out: list[dict[str, Any]] = []
    for row in (data.get("datasets") or [])[:6]:
        evid = str(row.get("EVID") or "")
        info = details.get(evid) or {}
        mag = row.get("MAGNITUDE")
        region = row.get("REGIONNAME") or info.get("Location") or ""
        evaluation = (info.get("evaluation") or "").strip()
        raw_title = (info.get("bulletinTitle") or "").strip(" .")
        body = evaluation or f"INCOIS ITEWS event M{mag} at {region} ({row.get('ORIGINTIME')})."
        threat = _threat(f"{raw_title} {body}")
        if threat:
            title = f"ITEWS tsunami threat · M{mag} {region}".strip()
        elif "does not exist" in body.lower() or "no tsunami" in body.lower():
            title = f"ITEWS M{mag} {region} — no tsunami threat for India".strip()
        else:
            title = f"ITEWS M{mag} {region}".strip()
        out.append(
            {
                "id": evid,
                "title": title[:160],
                "body": body[:400],
                "link": row.get("detail") or "",
                "mag": mag,
                "region": region,
                "origin": row.get("ORIGINTIME"),
                "lat": row.get("LATITUDE"),
                "lon": row.get("LONGITUDE"),
                "threat": threat,
                "source": "INCOIS ITEWS",
            }
        )
    return out


def _event_info(payload: Any) -> dict:
    if isinstance(payload, list) and payload:
        infos = (payload[0] or {}).get("event_info") or []
        if infos and isinstance(infos[0], dict):
            return infos[0]
    if isinstance(payload, dict):
        infos = payload.get("event_info") or []
        if infos and isinstance(infos[0], dict):
            return infos[0]
    return {}


async def incois_tsunami() -> tuple[list[dict[str, Any]], str]:
    hit = cache.get("incois:tsunami")
    if hit is not None:
        return hit, "ok" if hit else "empty"
    items: list[dict[str, Any]] = []
    try:
        async with httpx.AsyncClient(timeout=8.0, verify=False, follow_redirects=True) as c:
            r = await c.get(INCOIS_CATALOG)
            r.raise_for_status()
            data = r.json()
            rows = (data.get("datasets") or [])[:4]

            async def _detail(row: dict) -> tuple[str, dict]:
                evid = str(row.get("EVID") or "")
                url = row.get("detail")
                if not url:
                    return evid, {}
                try:
                    d = await c.get(url)
                    if d.status_code != 200:
                        return evid, {}
                    return evid, _event_info(d.json())
                except Exception:
                    return evid, {}

            pairs = await asyncio.gather(*[_detail(row) for row in rows[:2]])
            details = {k: v for k, v in pairs if v}
            items = parse_incois_catalog(data, details)
    except Exception:
        items = []

    if not items:
        for url in INCOIS_FEEDS:
            try:
                r = await client().get(url, timeout=6.0)
                if r.status_code != 200:
                    continue
                root = ET.fromstring(r.text)
                for it in root.findall(".//item")[:6]:
                    items.append(
                        {
                            "title": (it.findtext("title") or "").strip(),
                            "body": (it.findtext("description") or "").strip()[:400],
                            "link": (it.findtext("link") or "").strip(),
                            "source": "INCOIS ITEWS",
                            "threat": _threat((it.findtext("title") or "") + (it.findtext("description") or "")),
                        }
                    )
                if items:
                    break
            except Exception:
                continue

    cache.set("incois:tsunami", items, 10 * 60)
    return items, "ok" if items else "empty"

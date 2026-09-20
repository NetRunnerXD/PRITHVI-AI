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
from app.data.india_mask import in_india
from app.providers.http import client

USGS = "https://earthquake.usgs.gov/fdsnws/event/1/query"
INCOIS_CATALOG = "https://tsunami.incois.gov.in/itews/DSSProducts/OPR/past90days.json"
INCOIS_FEEDS = (
    "https://tsunami.incois.gov.in/itews/DSS/eqrss.xml",
    "https://tsunami.incois.gov.in/TEWS/eqrss.xml",
)


def _parse_quake_time(q: dict[str, Any]) -> datetime | None:
    raw = q.get("time_iso") or q.get("origin") or q.get("time")
    if isinstance(raw, (int, float)):
        try:
            ms = float(raw)
            if ms > 1e12:
                ms /= 1000.0
            return datetime.fromtimestamp(ms, tz=timezone.utc)
        except (OSError, OverflowError, ValueError):
            return None
    if not raw:
        return None
    s = str(raw).strip().replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(s)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except ValueError:
        return None


def felt_radius_km(mag: float | None) -> float:
    m = float(mag or 0)
    if m < 3.5:
        return 80.0
    if m < 4.5:
        return 180.0
    if m < 5.5:
        return 350.0
    if m < 6.5:
        return 600.0
    return 1200.0


def quake_affects_pin(q: dict[str, Any], lat: float, lon: float, now: datetime | None = None) -> bool:
    """Keep only recent events that can be felt or tsunami-relevant at the pin."""
    now = now or datetime.now(timezone.utc)
    mag = q.get("mag")
    try:
        mag_f = float(mag) if mag is not None else 0.0
    except (TypeError, ValueError):
        mag_f = 0.0
    when = _parse_quake_time(q)
    max_age_h = 168.0 if mag_f >= 6.0 else 72.0
    if when is not None:
        age_h = (now - when.astimezone(timezone.utc)).total_seconds() / 3600.0
        if age_h < -2 or age_h > max_age_h:
            return False
    dist = q.get("distance_km")
    if dist is None and q.get("lat") is not None and q.get("lon") is not None:
        try:
            dist = _km(lat, lon, float(q["lat"]), float(q["lon"]))
        except (TypeError, ValueError):
            dist = None
    if dist is None:
        return False
    if mag_f >= 6.5 and dist <= 1500:
        return True
    return float(dist) <= felt_radius_km(mag_f)


def filter_quakes_for_pin(quakes: list[dict[str, Any]], lat: float, lon: float) -> list[dict[str, Any]]:
    now = datetime.now(timezone.utc)
    kept = [q for q in quakes if quake_affects_pin(q, lat, lon, now)]
    kept.sort(
        key=lambda x: (
            _parse_quake_time(x) is None,
            -(_parse_quake_time(x) or datetime(1970, 1, 1, tzinfo=timezone.utc)).timestamp(),
            x.get("distance_km") is None,
            x.get("distance_km") or 1e9,
        )
    )
    return kept


def tsunami_affects_pin(
    item: dict[str, Any],
    *,
    coast_km: float | None,
    inland: bool,
    now: datetime | None = None,
) -> bool:
    now = now or datetime.now(timezone.utc)
    if item.get("threat"):
        if inland and coast_km is not None and coast_km > 200:
            return False
        return True
    if inland or (coast_km is not None and coast_km > 120):
        return False
    when = _parse_quake_time(item)
    if when is None:
        return False
    age_h = (now - when.astimezone(timezone.utc)).total_seconds() / 3600.0
    if age_h > 72:
        return False
    mag = item.get("mag")
    try:
        mag_f = float(mag) if mag is not None else 0.0
    except (TypeError, ValueError):
        mag_f = 0.0
    return mag_f >= 6.0


def filter_tsunami_for_pin(
    items: list[dict[str, Any]],
    *,
    coast_km: float | None = None,
    inland: bool = False,
) -> list[dict[str, Any]]:
    now = datetime.now(timezone.utc)
    return [t for t in items if tsunami_affects_pin(t, coast_km=coast_km, inland=inland, now=now)]


def _quake_india(q: dict[str, Any]) -> bool:
    place = (q.get("place") or "").lower()
    if any(x in place for x in ("indonesia", "sumatra", "java", "philippines", "myanmar", "burma", "bangladesh")):
        if "india" not in place and "andaman" not in place:
            return False
    lat, lon = q.get("lat"), q.get("lon")
    if lat is not None and lon is not None:
        try:
            if in_india(float(lat), float(lon)):
                return True
        except (TypeError, ValueError):
            pass
    return any(x in place for x in ("india", "andaman", "nicobar", "lakshadweep"))


def _km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371.0
    p1, p2 = radians(lat1), radians(lat2)
    dp, dl = radians(lat2 - lat1), radians(lon2 - lon1)
    a = sin(dp / 2) ** 2 + cos(p1) * cos(p2) * sin(dl / 2) ** 2
    return 2 * r * atan2(sqrt(a), sqrt(max(0.0, 1 - a)))


def _csv_num(v: Any) -> float | None:
    if v is None:
        return None
    s = str(v).strip()
    if s == "":
        return None
    try:
        return float(s)
    except (TypeError, ValueError):
        return None


def parse_usgs_csv(text: str, lat: float, lon: float) -> list[dict[str, Any]]:
    import csv
    import io

    out: list[dict[str, Any]] = []
    reader = csv.DictReader(io.StringIO(text or ""))
    for row in reader:
        elat = _csv_num(row.get("latitude"))
        elon = _csv_num(row.get("longitude"))
        dist = None
        if elat is not None and elon is not None:
            dist = round(_km(lat, lon, elat, elon), 0)
        out.append(
            {
                "id": (row.get("id") or "").strip() or None,
                "mag": _csv_num(row.get("mag")),
                "magType": (row.get("magType") or "").strip() or None,
                "place": (row.get("place") or "").strip() or None,
                "time_iso": (row.get("time") or "").strip() or None,
                "updated_iso": (row.get("updated") or "").strip() or None,
                "lat": elat,
                "lon": elon,
                "depth_km": _csv_num(row.get("depth")),
                "distance_km": dist,
                "nst": _csv_num(row.get("nst")),
                "gap": _csv_num(row.get("gap")),
                "dmin": _csv_num(row.get("dmin")),
                "rms": _csv_num(row.get("rms")),
                "net": (row.get("net") or "").strip() or None,
                "type": (row.get("type") or "").strip() or None,
                "locationSource": (row.get("locationSource") or "").strip() or None,
                "magSource": (row.get("magSource") or "").strip() or None,
                "horizontalError": _csv_num(row.get("horizontalError")),
                "depthError": _csv_num(row.get("depthError")),
                "magError": _csv_num(row.get("magError")),
                "magNst": _csv_num(row.get("magNst")),
                "status": (row.get("status") or "").strip() or None,
                "source": "USGS FDSN CSV (India–Indian Ocean box; NCS has no public JSON)",
                "tsunami_flag": False,
            }
        )
    return out


def seed_usgs_csv(csv_text: str | None) -> bool:
    if not csv_text or not str(csv_text).strip():
        return False
    cache.set("usgs:india:csv", str(csv_text), 10 * 60)
    return True


async def recent_quakes(lat: float, lon: float, limit: int = 8) -> tuple[list[dict[str, Any]], str]:
    hit = cache.get("usgs:india:csv")
    if hit is None:
        params = {
            "format": "csv",
            "minlatitude": 6.5,
            "maxlatitude": 37.5,
            "minlongitude": 68,
            "maxlongitude": 97.5,
            "orderby": "time",
            "limit": 20,
            "starttime": (datetime.now(timezone.utc) - timedelta(days=14)).strftime("%Y-%m-%d"),
        }
        try:
            r = await client().get(USGS, params=params, timeout=10.0)
            r.raise_for_status()
            hit = r.text
            cache.set("usgs:india:csv", hit, 10 * 60)
        except Exception:
            return [], "error"
    out = parse_usgs_csv(hit if isinstance(hit, str) else "", lat, lon)
    out = [q for q in out if _quake_india(q)]
    emsc, _ = await emsc_quakes(lat, lon, limit=max(limit, 8))
    merged = _merge_quakes(out, emsc)
    merged = filter_quakes_for_pin(merged, lat, lon)
    return merged[:limit], "ok" if merged else "empty"


EMSC = "https://www.seismicportal.eu/fdsnws/event/1/query"


def _merge_quakes(a: list[dict[str, Any]], b: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    out: list[dict[str, Any]] = []
    for row in a + b:
        mag = row.get("mag")
        t = row.get("time_iso") or row.get("time")
        place = (row.get("place") or "")[:40]
        key = f"{t}|{mag}|{place}"
        if key in seen:
            continue
        seen.add(key)
        out.append(row)
    return out


async def emsc_quakes(lat: float, lon: float, limit: int = 8) -> tuple[list[dict[str, Any]], str]:
    hit = cache.get("emsc:india")
    if hit is None:
        params = {
            "format": "json",
            "minlat": 6.5,
            "maxlat": 37.5,
            "minlon": 68,
            "maxlon": 97.5,
            "orderby": "time",
            "limit": 20,
            "starttime": (datetime.now(timezone.utc) - timedelta(days=7)).strftime("%Y-%m-%d"),
        }
        try:
            r = await client().get(EMSC, params=params, timeout=8.0)
            r.raise_for_status()
            hit = r.json()
            cache.set("emsc:india", hit, 10 * 60)
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
        elif isinstance(ms, str):
            time_iso = ms
        out.append(
            {
                "id": f.get("id") or props.get("unid"),
                "mag": mag,
                "magType": props.get("magtype") or props.get("magType"),
                "place": props.get("flynn_region") or props.get("place"),
                "time": ms,
                "time_iso": time_iso,
                "lat": elat,
                "lon": elon,
                "depth_km": depth,
                "distance_km": dist,
                "net": props.get("auth") or "EMSC",
                "type": props.get("type") or "earthquake",
                "status": props.get("status"),
                "source": "EMSC FDSN (India–Indian Ocean box; not NCS)",
                "tsunami_flag": False,
            }
        )
    out = [q for q in out if _quake_india(q)]
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

"""Observed lightning: Weatherbit current (45 min) + optional history + memory.

Prefer LIGHTNING_FEED_URL with {south}{west}{north}{east} or min/max query params.
Else Weatherbit at a few hubs (vendor caps radius at 75 km). History costs 10
quota units per call, so it is cached for the calendar day and limited to 2 hubs.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from typing import Any
from urllib.parse import urlparse

from app import cache
from app.config import ROOT, get_settings
from app.providers import weatherbit_lightning
from app.providers.http import client

STROKE_MEM = ROOT / ".cache" / "wb_strokes.json"
IST = timezone(timedelta(hours=5, minutes=30))


def _in_box(lat: float, lon: float, south: float, west: float, north: float, east: float) -> bool:
    return south <= lat <= north and west <= lon <= east


def parse_rows(payload: Any) -> list[dict[str, Any]]:
    if payload is None:
        return []
    if isinstance(payload, list):
        rows = payload
    elif isinstance(payload, dict):
        rows = payload.get("lightning") or payload.get("data") or payload.get("strikes") or payload.get("features") or []
        if isinstance(rows, dict):
            rows = [rows]
    else:
        return []
    out: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        geom = row.get("geometry") or {}
        coords = geom.get("coordinates") if isinstance(geom, dict) else None
        lat = row.get("lat") or row.get("latitude") or row.get("y")
        lon = row.get("lon") or row.get("longitude") or row.get("lng") or row.get("x")
        if lat is None and isinstance(coords, (list, tuple)) and len(coords) >= 2:
            lon, lat = coords[0], coords[1]
        props = row.get("properties") if isinstance(row.get("properties"), dict) else {}
        try:
            lat_f, lon_f = float(lat), float(lon)
        except (TypeError, ValueError):
            continue
        ts = row.get("t") or row.get("time") or row.get("timestamp") or props.get("time")
        out.append({"lat": lat_f, "lon": lon_f, "t": str(ts) if ts else None, "source": "lightning-feed"})
    return out


async def fetch_bbox(south: float, west: float, north: float, east: float) -> dict[str, Any]:
    settings = get_settings()
    ck = f"ltn:bbox:{round(south, 1)}:{round(west, 1)}:{round(north, 1)}:{round(east, 1)}"
    hit = cache.get(ck)
    if isinstance(hit, dict):
        return hit
    url = (settings.lightning_feed_url or "").strip()
    key = settings.lightning_feed_key or settings.weatherbit_api_key
    if url:
        filled = (
            url.replace("{south}", str(south))
            .replace("{west}", str(west))
            .replace("{north}", str(north))
            .replace("{east}", str(east))
            .replace("{key}", key or "")
        )
        try:
            params: dict[str, Any] = {}
            parsed = urlparse(filled)
            if "{south}" not in url and "bbox" not in filled.lower():
                params = {"min_lat": south, "min_lon": west, "max_lat": north, "max_lon": east}
                if key and "key=" not in filled:
                    params["key"] = key
            r = await client().get(filled, params=params or None)
            if r.status_code == 429:
                weatherbit_lightning.mark_rate_limited(3600)
                out = {"ok": False, "status": "rate_limited", "strokes": [], "source": parsed.netloc or "lightning-feed"}
                cache.set(ck, out, 1800)
                return out
            r.raise_for_status()
            payload = r.json() if "json" in (r.headers.get("content-type") or "") else {}
            strokes = [s for s in parse_rows(payload) if _in_box(s["lat"], s["lon"], south, west, north, east)]
            out = {"ok": True, "status": "ok", "strokes": strokes[:200], "n": len(strokes), "source": parsed.netloc or "lightning-feed"}
            cache.set(ck, out, 180)
            return out
        except Exception:
            out = {"ok": False, "status": "error", "strokes": [], "source": "lightning-feed"}
            cache.set(ck, out, 120)
            return out

    lat = (south + north) / 2
    lon = (west + east) / 2
    diag = ((north - south) ** 2 + (east - west) ** 2) ** 0.5 * 111.3
    pack = await weatherbit_lightning.fetch(lat, lon, radius_km=min(280.0, max(75.0, diag / 2)))
    strokes = [s for s in (pack.get("strokes") or []) if _in_box(float(s["lat"]), float(s["lon"]), south, west, north, east)]
    out = {
        "ok": bool(pack.get("ok")),
        "status": pack.get("status") or "ok",
        "strokes": strokes,
        "n": len(strokes),
        "source": pack.get("source") or "weatherbit-lightning",
    }
    cache.set(ck, out, 180)
    return out


def _load_mem() -> list[dict[str, Any]]:
    if not STROKE_MEM.exists():
        return []
    try:
        blob = json.loads(STROKE_MEM.read_text(encoding="utf-8"))
        return blob if isinstance(blob, list) else []
    except (OSError, json.JSONDecodeError):
        return []


def _save_mem(rows: list[dict[str, Any]]) -> None:
    try:
        STROKE_MEM.parent.mkdir(parents=True, exist_ok=True)
        STROKE_MEM.write_text(json.dumps(rows[-400:]), encoding="utf-8")
    except OSError:
        pass


def remember_strokes(rows: list[dict[str, Any]], now: datetime) -> list[dict[str, Any]]:
    """Keep Weatherbit flashes for 6 h so they stay on the map after the 45-min window."""
    import os

    if os.environ.get("PYTEST_CURRENT_TEST"):
        return rows
    cutoff = now - timedelta(hours=6)
    mem = _load_mem()
    seen: set[tuple[float, float, str]] = set()
    kept: list[dict[str, Any]] = []
    for s in mem + rows:
        try:
            lat, lon = float(s["lat"]), float(s["lon"])
        except (KeyError, TypeError, ValueError):
            continue
        t = str(s.get("t") or s.get("timestamp_utc") or "")
        sig = (round(lat, 3), round(lon, 3), t[:16])
        if sig in seen:
            continue
        started = None
        if t:
            try:
                started = datetime.fromisoformat(t.replace("Z", "+00:00"))
                if started.tzinfo is None:
                    started = started.replace(tzinfo=timezone.utc)
            except ValueError:
                started = None
        if started is None and s.get("past_mins") is not None:
            try:
                started = now - timedelta(minutes=float(s["past_mins"]))
            except (TypeError, ValueError):
                started = now
        if started is None:
            started = now
        if started < cutoff:
            continue
        seen.add(sig)
        kept.append({**s, "lat": lat, "lon": lon, "t": t or started.isoformat(), "phase": "past", "kind": "lightning"})
    _save_mem(kept)
    return kept


async def fetch_hubs(
    hubs: list[dict[str, Any]],
    *,
    history: bool = True,
    frame: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Current lightning at hubs, plus at most two history calls for today."""
    import asyncio

    extra: list[dict[str, Any]] = []
    extra_status = None
    if frame and (get_settings().lightning_feed_url or "").strip():
        bbox = await fetch_bbox(frame["south"], frame["west"], frame["north"], frame["east"])
        extra = list(bbox.get("strokes") or [])
        extra_status = bbox.get("status")

    if not hubs:
        now = datetime.now(timezone.utc)
        strokes = remember_strokes(extra, now)
        return {
            "ok": bool(strokes),
            "status": extra_status or "no_hubs",
            "strokes": strokes[:200],
            "n": len(strokes),
            "source": "lightning-feed",
        }
    cur_packs = await asyncio.gather(
        *[weatherbit_lightning.fetch(float(h["lat"]), float(h["lon"]), radius_km=75.0) for h in hubs]
    )
    strokes: list[dict[str, Any]] = []
    status = "ok"
    for pack in cur_packs:
        if pack.get("status") == "rate_limited":
            status = "rate_limited"
        for s in pack.get("strokes") or []:
            strokes.append({**s, "phase": "past", "kind": "lightning", "window": "current_45m"})
    hist_n = 0
    if history and status != "rate_limited" and not weatherbit_lightning.rate_limited():
        today = datetime.now(IST).date().isoformat()
        hist_hubs = hubs[:2]
        hist_packs = await asyncio.gather(
            *[weatherbit_lightning.fetch_history(float(h["lat"]), float(h["lon"]), date=today) for h in hist_hubs]
        )
        for pack in hist_packs:
            if pack.get("status") == "rate_limited":
                status = "rate_limited"
            hist_n += int(pack.get("n") or 0)
            for s in pack.get("strokes") or []:
                strokes.append({**s, "phase": "past", "kind": "lightning", "window": "history_today"})
    now = datetime.now(timezone.utc)
    if extra_status == "rate_limited":
        status = "rate_limited"
    strokes = remember_strokes(extra + strokes, now)
    return {
        "ok": bool(strokes) or status == "ok",
        "status": status,
        "strokes": strokes[:200],
        "n": len(strokes),
        "source": "weatherbit-lightning",
        "history_n": hist_n,
        "hubs": len(hubs),
    }

"""Weatherbit current lightning. Live strokes, not a model watch."""

from __future__ import annotations

import time
from typing import Any

from app import cache
from app.config import get_settings
from app.providers.http import client

URL = "https://api.weatherbit.io/v2.0/current/lightning"
HIST = "https://api.weatherbit.io/v2.0/history/lightning"
_RATE_LIMIT_UNTIL = 0.0


def _f(v: Any) -> float | None:
    try:
        if v is None or v == "":
            return None
        return float(v)
    except (TypeError, ValueError):
        return None


def rate_limited() -> bool:
    return time.time() < _RATE_LIMIT_UNTIL


def mark_rate_limited(seconds: float = 3600.0) -> None:
    global _RATE_LIMIT_UNTIL
    _RATE_LIMIT_UNTIL = time.time() + seconds


def parse_payload(data: dict[str, Any], lat: float, lon: float) -> dict[str, Any]:
    rows = data.get("lightning") or data.get("data") or []
    if isinstance(rows, dict):
        rows = [rows]
    strokes: list[dict[str, Any]] = []
    for row in rows if isinstance(rows, list) else []:
        if not isinstance(row, dict):
            continue
        slat = _f(row.get("lat") or row.get("latitude"))
        slon = _f(row.get("lon") or row.get("longitude") or row.get("lng"))
        dist = _f(row.get("distance") or row.get("distance_km") or row.get("dist"))
        ts = row.get("timestamp_utc") or row.get("datetime") or row.get("timestamp") or row.get("time")
        if slat is None or slon is None:
            continue
        if dist is None:
            dlat = slat - lat
            dlon = slon - lon
            dist = round((dlat * dlat + dlon * dlon) ** 0.5 * 111.3, 1)
        past_mins = _f(row.get("past_mins"))
        strokes.append(
            {
                "lat": slat,
                "lon": slon,
                "distance_km": round(float(dist), 1),
                "t": str(ts) if ts else None,
                "timestamp_utc": str(row.get("timestamp_utc") or "") or None,
                "past_mins": past_mins,
                "wb_type": row.get("type") or row.get("source"),
                "source": "weatherbit-lightning",
                "phase": "past",
                "kind": "lightning",
            }
        )
    strokes.sort(key=lambda s: (s.get("past_mins") is None, s.get("past_mins") or 0, s["distance_km"]))
    nearest = strokes[0] if strokes else None
    return {
        "ok": True,
        "source": "weatherbit-lightning",
        "n": len(strokes),
        "strokes": strokes[:80],
        "nearest_km": None if nearest is None else nearest["distance_km"],
        "nearest": nearest,
        "status": "ok",
    }


def _good_key(ck: str) -> str:
    return f"{ck}:good"


def _last_good(ck: str, status: str) -> dict[str, Any] | None:
    good = cache.get(_good_key(ck))
    if isinstance(good, dict) and (good.get("strokes") or good.get("n")):
        return {**good, "status": status, "cached": True}
    return None


async def fetch(lat: float, lon: float, *, radius_km: float = 80.0) -> dict[str, Any]:
    settings = get_settings()
    key = settings.weatherbit_api_key
    ck = f"wb:ltn:{round(lat, 2)}:{round(lon, 2)}"
    empty = {"ok": False, "source": "weatherbit-lightning", "status": "missing_key", "n": 0, "strokes": []}
    if not key:
        return empty
    if rate_limited():
        return _last_good(ck, "rate_limited_cached") or {**empty, "status": "rate_limited"}
    hit = cache.get(ck)
    if isinstance(hit, dict) and hit.get("strokes"):
        return hit
    if isinstance(hit, dict) and hit.get("status") in {"rate_limited", "rate_limited_cached"}:
        return _last_good(ck, "rate_limited_cached") or hit
    try:
        r = await client().get(
            URL,
            params={
                "lat": lat,
                "lon": lon,
                "key": key,
                "search_distance_km": min(75, int(radius_km)),
                "search_mins": 45,
                "limit": 50,
                "sort": "time",
            },
        )
        if r.status_code == 429:
            mark_rate_limited(1800)
            cached = _last_good(ck, "rate_limited_cached")
            if cached:
                return cached
            out = {**empty, "status": "rate_limited"}
            cache.set(ck, out, 300)
            return out
        if r.status_code in {401, 403}:
            out = {**empty, "status": "unauthorized"}
            cache.set(ck, out, 300)
            return out
        r.raise_for_status()
        payload = r.json() if "json" in (r.headers.get("content-type") or "") else {}
        if not isinstance(payload, dict):
            payload = {}
        out = parse_payload(payload, lat, lon)
        if out["strokes"]:
            out["strokes"] = [s for s in out["strokes"] if s["distance_km"] <= max(radius_km, 75)]
            out["n"] = len(out["strokes"])
            out["nearest"] = out["strokes"][0] if out["strokes"] else None
            out["nearest_km"] = None if not out["nearest"] else out["nearest"]["distance_km"]
            cache.set(_good_key(ck), out, 6 * 3600)
        cache.set(ck, out, 180)
        return out
    except Exception:
        cached = _last_good(ck, "error_cached")
        if cached:
            return cached
        out = {**empty, "status": "error"}
        cache.set(ck, out, 120)
        return out


async def fetch_history(lat: float, lon: float, *, date: str, radius_km: float = 75.0) -> dict[str, Any]:
    """One day's observed flashes. Costs 10 quota units. Cache hard."""
    settings = get_settings()
    key = settings.weatherbit_api_key
    if not key:
        return {"ok": False, "source": "weatherbit-lightning", "status": "missing_key", "n": 0, "strokes": []}
    ck = f"wb:hist:{date}:{round(lat, 1)}:{round(lon, 1)}"
    if rate_limited():
        return _last_good(ck, "rate_limited_cached") or {
            "ok": False,
            "source": "weatherbit-lightning",
            "status": "rate_limited",
            "n": 0,
            "strokes": [],
        }
    hit = cache.get(ck)
    if isinstance(hit, dict) and (hit.get("strokes") or hit.get("status") != "rate_limited"):
        return hit
    try:
        r = await client().get(
            HIST,
            params={
                "lat": lat,
                "lon": lon,
                "date": date,
                "key": key,
                "search_distance_km": min(75, int(radius_km)),
                "limit": 200,
                "sort": "time",
                "tz": "local",
            },
        )
        if r.status_code == 429:
            mark_rate_limited(1800)
            cached = _last_good(ck, "rate_limited_cached")
            if cached:
                return cached
            out = {"ok": False, "source": "weatherbit-lightning", "status": "rate_limited", "n": 0, "strokes": []}
            cache.set(ck, out, 300)
            return out
        if r.status_code in {401, 403}:
            out = {"ok": False, "source": "weatherbit-lightning", "status": "unauthorized", "n": 0, "strokes": []}
            cache.set(ck, out, 1800)
            return out
        r.raise_for_status()
        payload = r.json() if "json" in (r.headers.get("content-type") or "") else {}
        if not isinstance(payload, dict):
            payload = {}
        out = parse_payload(payload, lat, lon)
        out["date"] = date
        out["kind"] = "history"
        if out.get("strokes"):
            cache.set(_good_key(ck), out, 20 * 3600)
        cache.set(ck, out, 20 * 3600)
        return out
    except Exception:
        cached = _last_good(ck, "error_cached")
        if cached:
            return cached
        out = {"ok": False, "source": "weatherbit-lightning", "status": "error", "n": 0, "strokes": []}
        cache.set(ck, out, 600)
        return out

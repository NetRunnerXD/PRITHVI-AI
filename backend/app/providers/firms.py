"""NASA FIRMS VIIRS active-fire hotspots for India.

Public South-Asia 24 h CSV — no MAP_KEY. Thermal anomalies, not a burned-area
product. Clustered so the map is not a point cloud.
"""

from __future__ import annotations

import csv
import io
from datetime import datetime, timedelta, timezone
from typing import Any

from app import cache
from app.data.india_districts import nearest
from app.data.india_mask import in_india
from app.providers.http import client

IST = timezone(timedelta(hours=5, minutes=30))

CSV_URLS = (
    "https://firms.modaps.eosdis.nasa.gov/data/active_fire/suomi-npp-viirs-c2/csv/SUOMI_VIIRS_C2_South_Asia_24h.csv",
    "https://firms.modaps.eosdis.nasa.gov/data/active_fire/noaa-20-viirs-c2/csv/J1_VIIRS_C2_South_Asia_24h.csv",
)

# 0.18° ≈ 20 km bins.
BIN = 0.18


def _acq_utc(acq: str | None) -> datetime | None:
    raw = (acq or "").strip()
    if not raw:
        return None
    parts = raw.split()
    if len(parts) < 2:
        return None
    day, hm = parts[0], parts[1][:4]
    if len(hm) < 4:
        return None
    try:
        return datetime.strptime(f"{day}{hm}", "%Y-%m-%d%H%M").replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def _f(v: Any) -> float | None:
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def parse_csv(text: str) -> list[dict[str, Any]]:
    if not text or "latitude" not in text[:400].lower():
        return []
    rows = csv.DictReader(io.StringIO(text))
    out: list[dict[str, Any]] = []
    for row in rows:
        lat = _f(row.get("latitude") or row.get("Latitude"))
        lon = _f(row.get("longitude") or row.get("Longitude"))
        if lat is None or lon is None:
            continue
        if not in_india(lat, lon):
            continue
        frp = _f(row.get("frp") or row.get("FRP")) or 0.0
        bright = _f(row.get("bright_ti4") or row.get("brightness") or row.get("bright_t31"))
        conf = str(row.get("confidence") or row.get("Confidence") or "").strip().lower()
        acq = f"{row.get('acq_date') or ''} {row.get('acq_time') or ''}".strip()
        occurred = _acq_utc(acq)
        out.append(
            {
                "lat": lat,
                "lon": lon,
                "frp": round(frp, 2),
                "bright_k": None if bright is None else round(bright, 1),
                "confidence": conf or None,
                "daynight": (row.get("daynight") or "").strip() or None,
                "acq": acq or None,
                "t": occurred.isoformat(timespec="seconds") if occurred else None,
                "t_utc": occurred,
                "occurred_at": occurred.isoformat(timespec="seconds") if occurred else None,
                "occurred_ms": int(occurred.timestamp() * 1000) if occurred else None,
                "satellite": (row.get("satellite") or "").strip() or None,
                "source": "nasa-firms-viirs",
            }
        )
    return out


def cluster(points: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Bin nearby detections. Keep clusters with ≥2 hits or FRP ≥ 8 MW."""
    buckets: dict[tuple[int, int], list[dict[str, Any]]] = {}
    for p in points:
        key = (int(p["lat"] / BIN), int(p["lon"] / BIN))
        buckets.setdefault(key, []).append(p)
    out: list[dict[str, Any]] = []
    for (iy, ix), group in buckets.items():
        n = len(group)
        frp = sum(float(g.get("frp") or 0) for g in group)
        if n < 2 and frp < 8:
            continue
        lat = sum(g["lat"] for g in group) / n
        lon = sum(g["lon"] for g in group) / n
        place = nearest(lat, lon)
        label = ", ".join(x for x in (place.get("district"), place.get("state")) if x) or f"{lat:.2f}, {lon:.2f}"
        high = any(str(g.get("confidence") or "") in {"h", "high", "n"} for g in group) or frp >= 20
        times = [g.get("t_utc") for g in group if g.get("t_utc") is not None]
        occurred = max(times) if times else None
        iso = occurred.isoformat(timespec="seconds") if occurred else None
        out.append(
            {
                "id": f"firms-{iy}-{ix}",
                "kind": "fire",
                "phase": "live",
                "lat": round(lat, 3),
                "lon": round(lon, 3),
                "n": n,
                "frp_mw": round(frp, 1),
                "place": label,
                "district": place.get("district"),
                "state": place.get("state"),
                "high": high,
                "source": "nasa-firms-viirs",
                "source_kind": "satellite-thermal",
                "t": iso,
                "occurred_at": iso,
                "occurred_ms": int(occurred.timestamp() * 1000) if occurred else None,
            }
        )
    out.sort(key=lambda r: float(r.get("frp_mw") or 0), reverse=True)
    return out[:80]


async def fetch_india() -> dict[str, Any]:
    ck = "firms:in:24h"
    hit = cache.get(ck)
    if isinstance(hit, dict):
        return hit
    last = "empty"
    for url in CSV_URLS:
        try:
            r = await client().get(url, timeout=8.0)
        except Exception:
            last = "error"
            continue
        if r.status_code >= 400 or len(r.content) < 80:
            last = f"http_{r.status_code}"
            continue
        text = r.text if isinstance(r.text, str) else r.content.decode("utf-8", "ignore")
        pts = parse_csv(text)
        clusters = cluster(pts)
        pack = {
            "ok": True,
            "status": "ok",
            "n_raw": len(pts),
            "n": len(clusters),
            "fires": clusters,
            "source": "nasa-firms-viirs",
            "url": url,
            "as_of": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        }
        cache.set(ck, pack, 20 * 60)
        return pack
    fail = {"ok": False, "status": last, "n": 0, "n_raw": 0, "fires": [], "source": "nasa-firms-viirs"}
    cache.set(ck, fail, 90)
    return fail


def near_pin(fires: list[dict[str, Any]], lat: float, lon: float, km: float = 40.0) -> list[dict[str, Any]]:
    out = []
    for f in fires:
        d = ((float(f["lat"]) - lat) ** 2 + (float(f["lon"]) - lon) ** 2) ** 0.5 * 111.3
        if d <= km:
            out.append({**f, "distance_km": round(d, 1)})
    out.sort(key=lambda r: float(r.get("distance_km") or 9e9))
    return out

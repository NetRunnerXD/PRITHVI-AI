"""One-off scan of live Weatherbit lightning over India hubs."""

from __future__ import annotations

import asyncio

from app.config import get_settings
from app.data.india_districts import nearest as near_d
from app.data.india_towns import TOWNS
from app.providers.http import aclose, client


def nearest_town(lat: float, lon: float) -> dict | None:
    best = None
    best_d = 1e18
    for t in TOWNS:
        dd = (t["lat"] - lat) ** 2 + (t["lon"] - lon) ** 2
        if dd < best_d:
            best_d = dd
            best = t
    km = (best_d ** 0.5) * 111.3 if best else 999
    if best and km <= 40:
        return {**best, "km": round(km, 1)}
    return None

HUBS = [
    ("Kolkata belt", 22.57, 88.36),
    ("Northeast", 26.18, 91.75),
    ("Delhi NCR", 28.61, 77.21),
    ("Mumbai", 19.08, 72.88),
    ("Chennai", 13.08, 80.27),
    ("Bengaluru", 12.97, 77.59),
    ("Hyderabad", 17.39, 78.49),
    ("Odisha", 20.27, 85.84),
    ("Gujarat", 23.03, 72.58),
    ("Bihar", 25.61, 85.14),
]


async def one(name: str, lat: float, lon: float, key: str):
    r = await client().get(
        "https://api.weatherbit.io/v2.0/current/lightning",
        params={
            "lat": lat,
            "lon": lon,
            "key": key,
            "search_distance_km": 280,
            "search_mins": 30,
            "limit": 8,
            "sort": "distance",
        },
    )
    if r.status_code != 200:
        return name, r.status_code, []
    data = r.json() if "json" in (r.headers.get("content-type") or "") else {}
    rows = data.get("data") or data.get("lightning") or []
    if isinstance(rows, dict):
        rows = [rows]
    out = []
    for row in rows or []:
        if not isinstance(row, dict):
            continue
        slat = row.get("lat") or row.get("latitude")
        slon = row.get("lon") or row.get("longitude")
        dist = row.get("distance") or row.get("distance_km")
        ts = row.get("timestamp_utc") or row.get("datetime") or row.get("time")
        if slat is None or slon is None:
            continue
        slat, slon = float(slat), float(slon)
        town = nearest_town(slat, slon)
        place = town["name"] if town else None
        d = near_d(slat, slon)
        district = f"{d.get('district')}, {d.get('state')}" if d else None
        label = place or district or f"{slat:.2f},{slon:.2f}"
        out.append((label, district, slat, slon, dist, ts))
    return name, 200, out


async def main() -> None:
    key = get_settings().weatherbit_api_key
    if not key:
        print("NO_KEY")
        return
    results = []
    for h in HUBS:
        results.append(await one(*h, key))
        await asyncio.sleep(0.2)
    await aclose()
    seen: set[tuple[float, float]] = set()
    for name, status, rows in results:
        print(f"HUB {name} status={status} n={len(rows)}")
        for label, district, slat, slon, dist, ts in rows:
            sig = (round(slat, 2), round(slon, 2))
            if sig in seen:
                continue
            seen.add(sig)
            print(f"HIT {label} | {district} | {slat:.3f},{slon:.3f} | {dist} km from hub | {ts}")


if __name__ == "__main__":
    asyncio.run(main())

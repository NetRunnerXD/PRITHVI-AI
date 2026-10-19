"""Active tropical cyclones for the map: observed track, forecast track, cone, category.

Sources (all public, no key):
* GDACS event list + per-event geometry (track points, category segments, uncertainty
  cone; GDACS relays JTWC / RSMC advisories) — primary.
* IBTrACS v04r01 ACTIVE (NOAA NCEI) — observed fixes with agency winds (provisional).
* JTWC RSS and IMD RSMC New Delhi — linked as the official bulletins (not parsed: IMD
  bulletins are PDF/HTML pages without a stable machine format).
* Optional PN-Blend 12 h track (research weights extrapolation .35 / GFS .20 / IFS .45),
  for systems in the North Indian Ocean only, using Open-Meteo GFS / ECMWF IFS MSLP grids.

Server-side cached: list 10 min, geometry 30 min, IBTrACS 1 h, PN-Blend 3 h.
"""

from __future__ import annotations

import asyncio
import csv
import io
import math
from datetime import datetime, timedelta, timezone
from typing import Any

from app import cache
from app.providers.http import client

GDACS_LIST = "https://www.gdacs.org/gdacsapi/api/events/geteventlist/SEARCH"
GDACS_GEOM = "https://www.gdacs.org/gdacsapi/api/polygons/getgeometry"
IBTRACS_ACTIVE = (
    "https://www.ncei.noaa.gov/data/international-best-track-archive-for-climate-stewardship-ibtracs/"
    "v04r01/access/csv/ibtracs.ACTIVE.list.v04r01.csv"
)
LINKS = {
    "imd_rsmc": "https://rsmcnewdelhi.imd.gov.in/",
    "jtwc": "https://www.metoc.navy.mil/jtwc/jtwc.html",
}
# Region the map cares about (Indian Ocean + adjoining W Pacific / S China Sea).
REGION = {"west": 30.0, "east": 150.0, "south": -40.0, "north": 45.0}
NIO = {"west": 40.0, "east": 100.0, "south": -5.0, "north": 32.0}


def _in(box: dict[str, float], lat: float, lon: float) -> bool:
    return box["south"] <= lat <= box["north"] and box["west"] <= lon <= box["east"]


def imd_category(kt: float | None) -> str | None:
    """IMD scale (3-min mean wind, kt)."""
    if kt is None:
        return None
    for lo, name in ((120, "SuCS"), (90, "ESCS"), (64, "VSCS"), (48, "SCS"), (34, "CS"), (28, "DD"), (17, "D")):
        if kt >= lo:
            return name
    return "LPA"


def ss_category(kt: float | None) -> str | None:
    if kt is None:
        return None
    for lo, name in ((137, "Cat 5"), (113, "Cat 4"), (96, "Cat 3"), (83, "Cat 2"), (64, "Cat 1"), (34, "TS")):
        if kt >= lo:
            return name
    return "TD"


def _centroid(coords: list) -> tuple[float, float] | None:
    ring = coords[0] if coords and isinstance(coords[0], list) and coords and isinstance(coords[0][0], list) else coords
    pts = [p for p in ring if isinstance(p, list) and len(p) >= 2]
    if not pts:
        return None
    return sum(p[1] for p in pts) / len(pts), sum(p[0] for p in pts) / len(pts)


def _key_time(key: str, year: int) -> datetime | None:
    # GDACS key "MMDDHHMM"
    try:
        return datetime(year, int(key[0:2]), int(key[2:4]), int(key[4:6]), int(key[6:8]), tzinfo=timezone.utc)
    except (ValueError, TypeError, IndexError):
        return None


def _iso(d: datetime | None) -> str | None:
    return d.isoformat().replace("+00:00", "Z") if d else None


def parse_geometry(geo: dict[str, Any]) -> dict[str, Any]:
    feats = list(geo.get("features") or [])
    adv_t = None
    pts: list[dict[str, Any]] = []
    segs: list[dict[str, Any]] = []
    cone = None
    for f in feats:
        p = f.get("properties") or {}
        g = f.get("geometry") or {}
        cls = str(p.get("Class") or "")
        if p.get("polygondate") and adv_t is None:
            try:
                adv_t = datetime.fromisoformat(p["polygondate"]).replace(tzinfo=timezone.utc)
            except ValueError:
                pass
        if cls.startswith("Point_Polygon_Point_"):
            c = _centroid(g.get("coordinates") or [])
            if c:
                pts.append({"i": int(cls.rsplit("_", 1)[-1]), "lat": round(c[0], 2), "lon": round(c[1], 2), "key": p.get("key")})
        elif cls.startswith("Line_Line_") and g.get("type") == "LineString":
            cs = g.get("coordinates") or []
            if cs:
                segs.append({"start": (cs[0][1], cs[0][0]), "cat": p.get("polygonlabel"), "forecast": bool(p.get("forecast"))})
        elif cls == "Poly_Cones" and g.get("type") in {"Polygon", "MultiPolygon"}:
            cone = g
    pts.sort(key=lambda r: r["i"])

    def seg_for(lat: float, lon: float) -> dict[str, Any]:
        # GDACS line order != point order: match the segment that starts at this point.
        best, bd = {}, 1e9
        for sg in segs:
            d = (sg["start"][0] - lat) ** 2 + (sg["start"][1] - lon) ** 2
            if d < bd:
                best, bd = sg, d
        return best if bd < 0.5 else {}

    year = (adv_t or datetime.now(timezone.utc)).year
    track = []
    prev_t = None
    for r in pts:
        t = _key_time(str(r.get("key") or ""), year)
        if t and prev_t and t < prev_t:  # crossed New Year
            t = t.replace(year=t.year + 1)
        prev_t = t or prev_t
        seg = seg_for(r["lat"], r["lon"]) or (track[-1] if track else {})
        fc = bool(t and adv_t and t > adv_t)
        track.append({"t": _iso(t), "lat": r["lat"], "lon": r["lon"], "cat": seg.get("cat"), "forecast": fc})
    return {
        "advisory_time": _iso(adv_t),
        "observed": [p for p in track if not p["forecast"]],
        "forecast": [p for p in track if p["forecast"]],
        "cone": cone,
    }


async def _gdacs_list() -> list[dict[str, Any]]:
    async def factory() -> list[dict[str, Any]]:
        now = datetime.now(timezone.utc)
        r = await client().get(
            GDACS_LIST,
            params={"eventlist": "TC", "fromDate": (now - timedelta(days=12)).strftime("%Y-%m-%d"), "toDate": (now + timedelta(days=1)).strftime("%Y-%m-%d")},
            timeout=6.0,
        )
        if r.status_code >= 400:
            return []
        return list((r.json() or {}).get("features") or [])

    return await cache.aget("cyc:gdacs:list", factory, ttl_s=600, swr_s=3600)


async def _gdacs_geom(eid: Any, ep: Any) -> dict[str, Any]:
    async def factory() -> dict[str, Any]:
        r = await client().get(GDACS_GEOM, params={"eventtype": "TC", "eventid": eid, "episodeid": ep}, timeout=10.0)
        if r.status_code >= 400:
            return {}
        return parse_geometry(r.json() or {})

    return await cache.aget(f"cyc:gdacs:geom:{eid}:{ep}", factory, ttl_s=1800, swr_s=6 * 3600)


async def _ibtracs() -> dict[str, list[dict[str, Any]]]:
    async def factory() -> dict[str, list[dict[str, Any]]]:
        r = await client().get(IBTRACS_ACTIVE, timeout=12.0)
        if r.status_code >= 400:
            return {}
        out: dict[str, list[dict[str, Any]]] = {}
        for row in csv.DictReader(io.StringIO(r.text)):
            name = (row.get("NAME") or "").strip()
            sid = (row.get("SID") or "").strip()
            if not sid or sid == "SID" or not row.get("LAT", "").strip():
                continue
            try:
                lat, lon = float(row["LAT"]), float(row["LON"])
            except ValueError:
                continue
            w = (row.get("WMO_WIND") or "").strip() or (row.get("USA_WIND") or "").strip()
            out.setdefault(name.upper(), []).append(
                {
                    "sid": sid,
                    "basin": (row.get("BASIN") or "").strip(),
                    "t": (row.get("ISO_TIME") or "").strip().replace(" ", "T") + "Z",
                    "lat": lat,
                    "lon": lon,
                    "wind_kt": float(w) if w and w.replace(".", "").isdigit() else None,
                    "agency": (row.get("WMO_AGENCY") or "").strip() or (row.get("USA_AGENCY") or "").strip() or None,
                }
            )
        return out

    try:
        return await cache.aget("cyc:ibtracs:active", factory, ttl_s=3600, swr_s=6 * 3600)
    except Exception:
        return {}


def _kmh_to_kt(v: Any) -> float | None:
    try:
        return round(float(v) / 1.852, 1)
    except (TypeError, ValueError):
        return None


async def active(region: str = "india") -> dict[str, Any]:
    box = REGION if region != "all" else {"west": -180.0, "east": 180.0, "south": -90.0, "north": 90.0}
    feats, ib = await asyncio.gather(_gdacs_list(), _ibtracs(), return_exceptions=True)
    feats = feats if isinstance(feats, list) else []
    ib = ib if isinstance(ib, dict) else {}
    systems: list[dict[str, Any]] = []
    sel = []
    for f in feats:
        p = f.get("properties") or {}
        coords = (f.get("geometry") or {}).get("coordinates") or [None, None]
        if str(p.get("iscurrent")).lower() != "true" or coords[0] is None:
            continue
        lat, lon = float(coords[1]), float(coords[0])
        if not _in(box, lat, lon):
            continue
        sel.append((p, lat, lon))
    geoms = await asyncio.gather(*[_gdacs_geom(p.get("eventid"), p.get("episodeid")) for p, _, _ in sel], return_exceptions=True)
    for (p, lat, lon), geo in zip(sel, geoms):
        geo = geo if isinstance(geo, dict) else {}
        name = str(p.get("eventname") or p.get("name") or "").strip()
        short = name.split("-")[0].upper()
        kt = _kmh_to_kt((p.get("severitydata") or {}).get("severity"))  # GDACS: peak over the event
        ib_track = ib.get(short) or []
        cur_cat = ((geo.get("observed") or [{}])[-1] or {}).get("cat")
        cur_kt = ib_track[-1]["wind_kt"] if ib_track and ib_track[-1].get("wind_kt") is not None else None
        nio = _in(NIO, lat, lon)
        sysd = {
            "id": f"gdacs-{p.get('eventid')}",
            "name": name,
            "lat": lat,
            "lon": lon,
            "basin": "NIO" if nio else (ib_track[-1]["basin"] if ib_track else None),
            "peak_wind_kt": kt,
            "current_category": cur_cat,
            "ibtracs_last_wind_kt": cur_kt,
            "peak_category": imd_category(kt) if nio else ss_category(kt),
            "category_scale": "IMD (peak)" if nio else "Saffir-Simpson (peak)",
            "severity_text": (p.get("severitydata") or {}).get("severitytext"),
            "alert_level": p.get("alertlevel"),
            "advisory_source": p.get("source"),
            "advisory_time": geo.get("advisory_time") or p.get("todate"),
            "updated": p.get("datemodified"),
            "observed_track": geo.get("observed") or [],
            "forecast_track": geo.get("forecast") or [],
            "cone": geo.get("cone"),
            "ibtracs": [
                {k: r[k] for k in ("t", "lat", "lon", "wind_kt", "agency")} for r in ib_track[-40:]
            ],
            "links": {"gdacs": (p.get("url") or {}).get("report"), **LINKS},
        }
        if nio:
            try:
                from app.science.pn.cyclone import blend_track

                sysd["pn_blend"] = await asyncio.wait_for(blend_track(sysd), timeout=12.0)
            except Exception as e:
                sysd["pn_blend"] = {"ok": False, "status": type(e).__name__}
        systems.append(sysd)
    return {
        "ok": True,
        "as_of": _iso(datetime.now(timezone.utc)),
        "region": region,
        "count": len(systems),
        "systems": systems,
        "sources": ["GDACS (JTWC/RSMC advisories)", "IBTrACS v04r01 ACTIVE (provisional)"],
        "links": LINKS,
        "note": "Official warnings for India: IMD RSMC New Delhi. Map tracks are informational.",
    }


def haversine_km(a: float, b: float, c: float, d: float) -> float:
    r = math.radians
    h = math.sin(r(c - a) / 2) ** 2 + math.cos(r(a)) * math.cos(r(c)) * math.sin(r(d - b) / 2) ** 2
    return 2 * 6371.0 * math.asin(math.sqrt(min(1.0, h)))

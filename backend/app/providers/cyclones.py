"""Active tropical cyclones for the map: observed track, forecast track, cone, category.

Sources (all public, no key):
* GDACS event list + per-event geometry (track points, category segments, uncertainty
  cone; GDACS relays JTWC / RSMC advisories) — primary.
* IBTrACS v04r01 ACTIVE (NOAA NCEI) — observed fixes with agency winds (provisional).
* JTWC RSS -> per-storm JMV 3.0 ".tcw" warnings (observed fixes, forecast track and 1-min
  winds) for every basin JTWC covers (W Pacific, N Indian Ocean, S Hemisphere, C/E Pacific).
* NHC CurrentStorms.json — Atlantic / E Pacific systems (current position and intensity).
* IMD RSMC New Delhi — linked as the official NIO bulletin (PDF/HTML, no stable machine format).
  JTWC / NHC-only systems get a cone from the NHC average track-error radii.
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
JTWC_RSS = "https://www.metoc.navy.mil/jtwc/rss/jtwc.rss"
NHC_CURRENT = "https://www.nhc.noaa.gov/CurrentStorms.json"
# NHC 2024 cone radii (nm, 2/3 of 5-yr official track errors) by forecast hour.
CONE_NM = ((0, 10), (12, 26), (24, 41), (36, 55), (48, 70), (60, 88), (72, 102), (96, 151), (120, 220))
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


def _latlon(tok_lat: str, tok_lon: str) -> tuple[float, float] | None:
    """JMV tokens like 159N / 1356E (tenths of a degree)."""
    try:
        la = int(tok_lat[:-1]) / 10.0 * (1 if tok_lat[-1] == "N" else -1)
        lo = int(tok_lon[:-1]) / 10.0 * (1 if tok_lon[-1] == "E" else -1)
    except (ValueError, IndexError):
        return None
    return la, lo


def parse_tcw(text: str) -> dict[str, Any] | None:
    """JTWC JMV 3.0 warning file -> {id, name, t0, observed[], forecast[]} (winds 1-min kt)."""
    import re

    lines = text.splitlines()
    head = next((ln for ln in lines if re.match(r"^\d{10} \w{3} ", ln)), None)
    if not head:
        return None  # formation alerts (TCFA) have no warning block
    parts = head.split()
    t0 = datetime.strptime(parts[0], "%Y%m%d%H").replace(tzinfo=timezone.utc)
    sid, name = parts[1], parts[2].title()
    fc: list[dict[str, Any]] = []
    for ln in lines:
        m = re.match(r"^T(\d{3}) (\d{2,3}[NS]) (\d{3,4}[EW]) (\d{3})", ln)
        if m:
            ll = _latlon(m.group(2), m.group(3))
            if ll:
                h = int(m.group(1))
                fc.append({"h": h, "t": _iso(t0 + timedelta(hours=h)), "lat": ll[0], "lon": ll[1], "wind_kt": float(m.group(4))})
    obs: dict[str, dict[str, Any]] = {}
    for ln in lines:
        m = re.match(r"^\d{2}(\d{8}) (\d{2,3}[NS])(\d{3,4}[EW]) +(\d{1,3})\s*$", ln)
        if m:
            ll = _latlon(m.group(2), m.group(3))
            try:
                t = datetime.strptime("20" + m.group(1), "%Y%m%d%H").replace(tzinfo=timezone.utc)
            except ValueError:
                continue
            if ll:
                obs[_iso(t) or ""] = {"t": _iso(t), "lat": ll[0], "lon": ll[1], "wind_kt": float(m.group(4)), "forecast": False}
    observed = sorted(obs.values(), key=lambda r: r["t"])
    if not fc and not observed:
        return None
    return {"id": sid, "name": name, "t0": _iso(t0), "observed": observed, "forecast": fc}


def cone_polygon(track: list[dict[str, Any]]) -> dict[str, Any] | None:
    """GeoJSON polygon around forecast points using the NHC average-error radii."""
    if len(track) < 2:
        return None

    def rad_nm(h: float) -> float:
        for (h0, r0), (h1, r1) in zip(CONE_NM, CONE_NM[1:]):
            if h <= h1:
                return r0 + (r1 - r0) * (h - h0) / (h1 - h0)
        return CONE_NM[-1][1]

    left, right = [], []
    n = len(track)
    for i, p in enumerate(track):
        a, b = track[max(0, i - 1)], track[min(n - 1, i + 1)]
        k = math.cos(math.radians(p["lat"]))
        dx, dy = (b["lon"] - a["lon"]) * k, b["lat"] - a["lat"]
        L = math.hypot(dx, dy) or 1.0
        nxv, nyv = -dy / L, dx / L  # left normal
        r = rad_nm(p.get("h", 0)) / 60.0
        left.append([round(p["lon"] + nxv * r / max(k, 0.2), 3), round(p["lat"] + nyv * r, 3)])
        right.append([round(p["lon"] - nxv * r / max(k, 0.2), 3), round(p["lat"] - nyv * r, 3)])
    # rounded cap at the far end
    e, r = track[-1], rad_nm(track[-1].get("h", 120)) / 60.0
    k = max(math.cos(math.radians(e["lat"])), 0.2)
    a0 = math.atan2(left[-1][1] - e["lat"], (left[-1][0] - e["lon"]) * k)
    cap = [
        [round(e["lon"] + r * math.cos(a0 - math.pi * j / 8) / k, 3), round(e["lat"] + r * math.sin(a0 - math.pi * j / 8), 3)]
        for j in range(1, 8)
    ]
    ring = left + cap + right[::-1]
    ring.append(ring[0])
    return {"type": "Polygon", "coordinates": [ring]}


async def _jtwc() -> list[dict[str, Any]]:
    async def factory() -> list[dict[str, Any]]:
        import re

        r = await client().get(JTWC_RSS, timeout=8.0)
        if r.status_code >= 400:
            return []
        urls = sorted(set(re.findall(r"https?://[^'\" <>]+?\.tcw", r.text)))

        async def one(u: str) -> dict[str, Any] | None:
            try:
                rr = await client().get(u, timeout=8.0)
                return parse_tcw(rr.text) if rr.status_code < 400 else None
            except Exception:
                return None

        got = await asyncio.gather(*[one(u) for u in urls[:12]])
        return [g for g in got if g]

    try:
        return await cache.aget("cyc:jtwc:v1", factory, ttl_s=1800, swr_s=6 * 3600)
    except Exception:
        return []


async def _nhc() -> list[dict[str, Any]]:
    async def factory() -> list[dict[str, Any]]:
        r = await client().get(NHC_CURRENT, timeout=8.0)
        if r.status_code >= 400:
            return []
        out = []
        for s in (r.json() or {}).get("activeStorms") or []:
            try:
                out.append(
                    {
                        "id": s.get("id"),
                        "name": str(s.get("name") or "").title(),
                        "classification": s.get("classification"),
                        "wind_kt": float(s.get("intensity")) if s.get("intensity") else None,
                        "pressure_hpa": float(s.get("pressure")) if s.get("pressure") else None,
                        "lat": float(s["latitudeNumeric"]),
                        "lon": float(s["longitudeNumeric"]),
                        "t": s.get("lastUpdate"),
                    }
                )
            except (KeyError, TypeError, ValueError):
                continue
        return out

    try:
        return await cache.aget("cyc:nhc:v1", factory, ttl_s=1800, swr_s=6 * 3600)
    except Exception:
        return []


def _kmh_to_kt(v: Any) -> float | None:
    try:
        return round(float(v) / 1.852, 1)
    except (TypeError, ValueError):
        return None


async def active(region: str = "india") -> dict[str, Any]:
    box = REGION if region != "all" else {"west": -180.0, "east": 180.0, "south": -90.0, "north": 90.0}
    feats, ib, jt, nhc = await asyncio.gather(_gdacs_list(), _ibtracs(), _jtwc(), _nhc(), return_exceptions=True)
    feats = feats if isinstance(feats, list) else []
    ib = ib if isinstance(ib, dict) else {}
    jt = jt if isinstance(jt, list) else []
    nhc = nhc if isinstance(nhc, list) else []
    now = datetime.now(timezone.utc)
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
        systems.append(sysd)

    def near(a: dict[str, Any], lat: float, lon: float, name: str) -> bool:
        nm = (a.get("name") or "").split("-")[0].upper()
        if name and nm == name.upper():
            return True
        return haversine_km(a["lat"], a["lon"], lat, lon) < 120

    # JTWC warnings: refresh a matching GDACS system (newer fixes/forecast) or add a new one.
    for j in jt:
        cur = (j["forecast"] or j["observed"])[0] if j["forecast"] else j["observed"][-1]
        if not _in(box, cur["lat"], cur["lon"]):
            continue
        kt = cur.get("wind_kt")
        nio = _in(NIO, cur["lat"], cur["lon"])
        fc = [dict(p, forecast=True) for p in j["forecast"] if p["h"] > 0]
        match = next((x for x in systems if near(x, cur["lat"], cur["lon"], j["name"])), None)
        if match is not None:
            match["jtwc"] = {"id": j["id"], "warning_time": j["t0"], "wind_kt": kt}
            if (match.get("advisory_time") or "") <= (j["t0"] or ""):
                match.update(lat=cur["lat"], lon=cur["lon"], advisory_time=j["t0"], advisory_source="JTWC", current_wind_kt=kt)
                match["current_category"] = imd_category(kt) if nio else ss_category(kt)
                if fc:
                    match["forecast_track"] = [{"t": p["t"], "lat": p["lat"], "lon": p["lon"], "wind_kt": p["wind_kt"], "forecast": True} for p in fc]
                    match["cone"] = cone_polygon([{"h": 0, **cur}] + fc)
            continue
        systems.append(
            {
                "id": f"jtwc-{j['id']}",
                "name": f"{j['name']} ({j['id']})",
                "lat": cur["lat"],
                "lon": cur["lon"],
                "basin": "NIO" if nio else {"W": "WP", "E": "EP", "C": "CP", "A": "NIO", "B": "NIO", "S": "SH", "P": "SH"}.get(j["id"][-1:], j["id"][-1:]),
                "current_wind_kt": kt,
                "current_category": imd_category(kt) if nio else ss_category(kt),
                "category_scale": "IMD (approx., from JTWC 1-min)" if nio else "Saffir-Simpson",
                "advisory_source": "JTWC",
                "advisory_time": j["t0"],
                "observed_track": j["observed"][-40:],
                "forecast_track": [{"t": p["t"], "lat": p["lat"], "lon": p["lon"], "wind_kt": p["wind_kt"], "forecast": True} for p in fc],
                "cone": cone_polygon([{"h": 0, **cur}] + fc),
                "links": {**LINKS},
            }
        )
    # NHC (Atlantic / E Pacific): add systems nobody else listed.
    for h in nhc:
        if not _in(box, h["lat"], h["lon"]):
            continue
        match = next((x for x in systems if near(x, h["lat"], h["lon"], h["name"])), None)
        if match is not None:
            match.setdefault("nhc", {"id": h["id"], "classification": h["classification"], "wind_kt": h["wind_kt"], "time": h["t"]})
            if h["t"] and (match.get("advisory_time") or "") < h["t"].replace(".000Z", "Z"):
                match.update(lat=h["lat"], lon=h["lon"], current_wind_kt=h["wind_kt"], advisory_time=h["t"].replace(".000Z", "Z"), advisory_source="NHC")
                match["current_category"] = ss_category(h["wind_kt"]) if h["classification"] not in {"PTC", "PC"} else "Post-tropical"
            continue
        systems.append(
            {
                "id": f"nhc-{h['id']}",
                "name": h["name"],
                "lat": h["lat"],
                "lon": h["lon"],
                "basin": (h["id"] or "")[:2].upper(),
                "current_wind_kt": h["wind_kt"],
                "current_category": ss_category(h["wind_kt"]),
                "category_scale": "Saffir-Simpson",
                "advisory_source": "NHC",
                "advisory_time": h["t"],
                "observed_track": [],
                "forecast_track": [],
                "cone": None,
                "links": {"nhc": "https://www.nhc.noaa.gov/", **LINKS},
            }
        )

    # Drop GDACS events whose last advisory is >30 h old and that no live warning confirms.
    def fresh(x: dict[str, Any]) -> bool:
        if x.get("jtwc") or x.get("nhc") or not str(x.get("id", "")).startswith("gdacs-"):
            return True
        try:
            t = datetime.fromisoformat(str(x.get("advisory_time")).replace("Z", "+00:00"))
        except ValueError:
            return True
        return now - t < timedelta(hours=30)

    stale = [x["name"] for x in systems if not fresh(x)]
    systems = [x for x in systems if fresh(x)]
    for sysd in systems:
        if sysd.get("basin") == "NIO":
            try:
                from app.science.pn.cyclone import blend_track

                sysd["pn_blend"] = await asyncio.wait_for(blend_track(sysd), timeout=12.0)
            except Exception as e:
                sysd["pn_blend"] = {"ok": False, "status": type(e).__name__}
    return {
        "ok": True,
        "as_of": _iso(datetime.now(timezone.utc)),
        "region": region,
        "count": len(systems),
        "systems": systems,
        "dropped_stale": stale,
        "sources": ["GDACS", "JTWC warnings", "NHC", "IBTrACS ACTIVE (provisional)"],
        "links": LINKS,
        "note": "Official warnings for India: IMD RSMC New Delhi. Map tracks are informational.",
    }


def haversine_km(a: float, b: float, c: float, d: float) -> float:
    r = math.radians
    h = math.sin(r(c - a) / 2) ** 2 + math.cos(r(a)) * math.cos(r(c)) * math.sin(r(d - b) / 2) ** 2
    return 2 * 6371.0 * math.asin(math.sqrt(min(1.0, h)))

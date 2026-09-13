"""MOSDAC Download API (mdapi) — search + SSO token download.

Wired from the MOSDAC user manual (config.json / mdapi.py):
https://mosdac.gov.in/downloadapi-manual
Search needs no login. Download uses username/password → gettoken → Bearer.
Daily cap 5000 files/user; we hard-stop at 400. Three bad passwords lock 1 h.
Do not keep HDF5 in Mongo (512 MB Atlas). Sample, write last_hem.json, delete the file.
"""

from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path
from typing import Any

from app import cache
from app.config import ROOT, get_settings

ARCHIVE = ROOT / ".cache" / "mosdac"
TOKEN_URL = "https://mosdac.gov.in/download_api/gettoken"
SEARCH_URL = "https://mosdac.gov.in/apios/datasets.json"
DOWNLOAD_URL = "https://mosdac.gov.in/download_api/download"
REFRESH_URL = "https://mosdac.gov.in/download_api/refresh-token"
LOGOUT_URL = "https://mosdac.gov.in/download_api/logout"

# INSAT-3DS / 3DR. 3DIMG_* search returns "Data unavailable" (retired).
DATASETS = ("3SIMG_L2B_HEM", "3SIMG_L2C_FOG", "3SIMG_L1B_STD", "3RIMG_L2B_HEM", "3RIMG_L1B_STD")
PRIORITY = ("3SIMG_L2B_HEM", "3SIMG_L2C_FOG")
L1B = {"3SIMG_L1B_STD", "3RIMG_L1B_STD"}
QUOTA_CAP = 400


class NotConfigured(RuntimeError):
    pass


def credentials_present() -> bool:
    s = get_settings()
    return bool(s.mosdac_user and s.mosdac_pass)


def status() -> dict:
    s = get_settings()
    ARCHIVE.mkdir(parents=True, exist_ok=True)
    n = len([p for p in ARCHIVE.rglob("*") if p.is_file() and p.suffix != ".json"])
    return {
        "credentials": credentials_present(),
        "base_url": bool(s.mosdac_base_url),
        "wired": credentials_present(),
        "archive_files": n,
        "search": SEARCH_URL,
        "products": list(DATASETS),
        "note": "MOSDAC SSO token + apios search + download_api. Latest granule metadata is live; HDF5 cached under .cache/mosdac.",
    }


def list_archive() -> list[str]:
    if not ARCHIVE.exists():
        return []
    return [str(p.relative_to(ARCHIVE)) for p in ARCHIVE.rglob("*") if p.is_file()][:40]


async def _token() -> dict[str, Any]:
    s = get_settings()
    if not credentials_present():
        return {"ok": False, "status": "not_configured"}
    hit = cache.get("mosdac:token")
    if isinstance(hit, dict) and hit.get("access_token"):
        return {"ok": True, **hit}
    from app.providers.http import client

    r = await client().post(TOKEN_URL, json={"username": s.mosdac_user, "password": s.mosdac_pass})
    if r.status_code == 429:
        import asyncio

        await asyncio.sleep(2.0)
        r = await client().post(TOKEN_URL, json={"username": s.mosdac_user, "password": s.mosdac_pass})
    if r.status_code >= 400:
        return {"ok": False, "status": f"http_{r.status_code}", "error": (r.text or "")[:180]}
    body = r.json() if r.headers.get("content-type", "").startswith("application/json") else {}
    tok = body.get("access_token")
    if not tok:
        return {"ok": False, "status": "no_token", "error": str(body)[:180]}
    pack = {"access_token": tok, "refresh_token": body.get("refresh_token")}
    cache.set("mosdac:token", pack, 50 * 60)
    return {"ok": True, **pack}


async def _refresh(pack: dict[str, Any]) -> dict[str, Any]:
    rt = pack.get("refresh_token")
    if not rt:
        cache.set("mosdac:token", None, 1)
        return await _token()
    from app.providers.http import client

    r = await client().post(REFRESH_URL, json={"refresh_token": rt})
    if r.status_code >= 400:
        cache.set("mosdac:token", None, 1)
        return await _token()
    body = r.json() if r.headers.get("content-type", "").startswith("application/json") else {}
    tok = body.get("access_token")
    if not tok:
        cache.set("mosdac:token", None, 1)
        return await _token()
    nxt = {"access_token": tok, "refresh_token": body.get("refresh_token") or rt}
    cache.set("mosdac:token", nxt, 50 * 60)
    return {"ok": True, **nxt}


async def logout() -> None:
    hit = cache.get("mosdac:token")
    tok = hit.get("access_token") if isinstance(hit, dict) else None
    cache.set("mosdac:token", None, 1)
    if not tok:
        return
    from app.providers.http import client

    try:
        await client().post(LOGOUT_URL, headers={"Authorization": f"Bearer {tok}"})
    except Exception:
        pass


async def search(dataset_id: str = "3SIMG_L1B_STD", count: int = 3) -> dict[str, Any]:
    from app.providers.http import client

    end = date.today()
    start = end - timedelta(days=2)
    params = {
        "datasetId": dataset_id,
        "startTime": start.isoformat(),
        "endTime": end.isoformat(),
        "count": str(count),
        "boundingBox": "68.0,6.5,97.5,37.0",
    }
    ck = f"mosdac:search:{dataset_id}:{start}"
    hit = cache.get(ck)
    if isinstance(hit, dict):
        return hit
    r = await client().get(SEARCH_URL, params=params)
    if r.status_code >= 400:
        r = await client().get(SEARCH_URL, params={"datasetId": dataset_id, "count": str(count)})
    if r.status_code >= 400:
        return {"ok": False, "status": f"http_{r.status_code}", "datasetId": dataset_id}
    try:
        body = r.json()
    except Exception:
        return {"ok": False, "status": "not_json", "datasetId": dataset_id}
    items = body.get("entries") or body.get("items") or body.get("data") or body.get("features") or []
    if not items and isinstance(body.get("result"), list):
        items = body["result"]
    out = {
        "ok": True,
        "datasetId": dataset_id,
        "totalResults": body.get("totalResults") or len(items),
        "itemsPerPage": body.get("itemsPerPage") or len(items),
        "totalSizeMB": body.get("totalSizeMB"),
        "granules": _slim_items(items)[:8],
    }
    cache.set(ck, out, 600)
    return out


def _slim_items(items: list) -> list[dict[str, Any]]:
    rows = []
    for it in items:
        if not isinstance(it, dict):
            continue
        rows.append(
            {
                "id": it.get("id") or it.get("gId") or it.get("recordId") or it.get("granuleId"),
                "identifier": it.get("identifier") or it.get("fileName") or it.get("name"),
                "date": it.get("updated") or it.get("dcDate") or it.get("prodDate") or it.get("startTime") or it.get("datetime"),
            }
        )
    return rows


async def search_latest() -> dict[str, Any]:
    last: dict[str, Any] = {"ok": False}
    for ds in DATASETS:
        pack = await search(ds, count=3)
        last = pack
        if pack.get("ok") and pack.get("granules"):
            return pack
    return last


async def download_granule(record_id: str, filename: str | None = None) -> dict[str, Any]:
    tok = await _token()
    if not tok.get("ok"):
        return tok
    from app.providers.http import client

    ARCHIVE.mkdir(parents=True, exist_ok=True)
    name = filename or f"{record_id}.h5"
    dest = ARCHIVE / Path(name).name
    if dest.exists() and dest.stat().st_size > 1024:
        mm_h = _sample_h5(dest, 22.07, 88.07)
        nbytes = dest.stat().st_size
        try:
            dest.unlink()
        except OSError:
            pass
        return {"ok": True, "bytes": nbytes, "cached": True, "mm_h": mm_h, "kept": False}
    headers = {"Authorization": f"Bearer {tok['access_token']}"}
    r = await client().get(
        DOWNLOAD_URL,
        params={"id": record_id, "gId": record_id},
        headers=headers,
        timeout=120.0,
    )
    if r.status_code in {401, 403}:
        tok = await _refresh(tok)
        if not tok.get("ok"):
            return tok
        r = await client().get(
            DOWNLOAD_URL,
            params={"id": record_id, "gId": record_id},
            headers={"Authorization": f"Bearer {tok['access_token']}"},
            timeout=120.0,
        )
    if r.status_code >= 400:
        return {"ok": False, "status": f"http_{r.status_code}", "error": (r.text or "")[:180]}
    dest.write_bytes(r.content)
    nbytes = dest.stat().st_size
    mm_h = None
    if dest.suffix.lower() in {".h5", ".hdf5", ".he5"} or "HEM" in dest.name.upper():
        mm_h = _sample_h5(dest, 22.07, 88.07)
        if mm_h is not None:
            try:
                (ARCHIVE / "last_hem.json").write_text(
                    json.dumps({"mm_h": mm_h, "t": date.today().isoformat(), "granule": name}),
                    encoding="utf-8",
                )
            except OSError:
                pass
    try:
        dest.unlink()
    except OSError:
        pass
    return {"ok": True, "bytes": nbytes, "cached": False, "mm_h": mm_h, "kept": False}


async def fetch_live() -> dict[str, Any]:
    """Auth + latest granule list for the snapshot. Does not pull full HDF5 each refresh."""
    st = status()
    if not credentials_present():
        return {"ok": False, "status": "not_configured", **st}
    tok = await _token()
    search_pack = await search_latest()
    return {
        **st,
        "ok": bool(search_pack.get("ok") and (search_pack.get("granules") or tok.get("ok"))),
        "auth": tok.get("ok"),
        "auth_status": tok.get("status"),
        "search": search_pack,
    }


def _ist_day() -> str:
    from datetime import datetime, timedelta, timezone

    ist = timezone(timedelta(hours=5, minutes=30))
    return datetime.now(ist).strftime("%Y-%m-%d")


def quota_snapshot() -> dict[str, Any]:
    day = _ist_day()
    used = 0
    skipped = 0
    try:
        from app.store import sat_mongo

        col = sat_mongo.col("mosdac_quota")
        if col is not None:
            doc = col.find_one({"day_ist": day}) or {}
            used = int(doc.get("used") or 0)
            skipped = int(doc.get("skipped_cached") or 0)
    except Exception:
        pass
    return {"day_ist": day, "used": used, "skipped_cached": skipped, "cap": QUOTA_CAP}


def _quota_inc(*, cached: bool) -> bool:
    day = _ist_day()
    try:
        from app.store import sat_mongo

        col = sat_mongo.col("mosdac_quota")
        if col is None:
            return True
        if cached:
            col.update_one({"day_ist": day}, {"$inc": {"skipped_cached": 1}, "$setOnInsert": {"used": 0, "cap": QUOTA_CAP}}, upsert=True)
            return True
        doc = col.find_one({"day_ist": day}) or {}
        if int(doc.get("used") or 0) >= QUOTA_CAP:
            return False
        col.update_one({"day_ist": day}, {"$inc": {"used": 1}, "$setOnInsert": {"skipped_cached": 0, "cap": QUOTA_CAP}}, upsert=True)
        return True
    except Exception:
        return True


async def ingest_latest(*, allow_l1b: bool = False) -> list[dict[str, Any]]:
    """Download newest granules that are not already in sat_frames. Counts against 400/day."""
    from app.store.sat_frames import has_granule, put_frame

    products = list(PRIORITY)
    if allow_l1b:
        products.extend(p for p in DATASETS if p in L1B)
    out: list[dict[str, Any]] = []
    for product in products:
        pack = await search(product, count=1)
        granules = pack.get("granules") or []
        if not granules or not granules[0].get("id"):
            out.append({"ok": False, "product": product, "status": "no_granule"})
            continue
        g = granules[0]
        gid = str(g["id"])
        if has_granule(gid):
            _quota_inc(cached=True)
            out.append({"ok": True, "product": product, "granule_id": gid, "cached": True, "status": "cached"})
            continue
        if product in L1B and not allow_l1b:
            out.append({"ok": False, "product": product, "status": "l1b_skipped"})
            continue
        if not _quota_inc(cached=False):
            out.append({"ok": False, "product": product, "status": "quota"})
            break
        dl = await download_granule(gid, g.get("identifier"))
        err = str(dl.get("error") or dl.get("status") or "")
        if "latency" in err.lower() or "3 days" in err.lower():
            out.append({"ok": False, "product": product, "status": "latency_3d", "error": err[:180]})
            continue
        if not dl.get("ok"):
            out.append({**dl, "product": product, "granule_id": gid})
            continue
        put_frame(
            {
                "source": "mosdac",
                "product": product,
                "granule_id": gid,
                "filename": g.get("identifier"),
                "started_at": g.get("date"),
                "bytes_raw": dl.get("bytes"),
                "quota_counted": not dl.get("cached"),
                "grid_kind": "rain_mm_h" if "HEM" in product else "tb_k" if "L1B" in product else "fog_mask",
                "mm_h": dl.get("mm_h"),
                "note": "HDF sampled then deleted — not stored in Mongo",
            }
        )
        out.append({**dl, "product": product, "granule_id": gid, "ok": True})
    try:
        await logout()
    except Exception:
        pass
    return out


async def download_product(product: str = "3SIMG_L2B_HEM") -> dict[str, Any]:
    pack = await search(product, count=1)
    granules = pack.get("granules") or []
    if not granules or not granules[0].get("id"):
        return {"ok": False, "status": "no_granule", **pack, **status()}
    g = granules[0]
    dl = await download_granule(str(g["id"]), g.get("identifier"))
    return {**dl, "granule": g, "search": pack}


def _scaled(ds):
    import numpy as np

    a = np.array(ds[()], dtype=float)
    fill = ds.attrs.get("_FillValue")
    if fill is not None:
        a = np.where(a == float(np.array(fill).reshape(-1)[0]), np.nan, a)
    sf = ds.attrs.get("scale_factor")
    off = ds.attrs.get("add_offset")
    if sf is not None:
        a = a * float(np.array(sf).reshape(-1)[0])
    if off is not None:
        a = a + float(np.array(off).reshape(-1)[0])
    return a


def _sample_h5(path: Path, lat: float, lon: float) -> float | None:
    try:
        import h5py
        import numpy as np
    except ImportError:
        return None
    try:
        with h5py.File(path, "r") as f:
            rain = None
            for key in ("HEM", "IMR", "rainfall", "Rainfall", "precipitation"):
                if key in f:
                    rain = f[key]
                    break
            if rain is None:
                return None
            a = _scaled(rain)
            while a.ndim > 2:
                a = a[0]
            if "Latitude" in f and "Longitude" in f:
                la = _scaled(f["Latitude"])
                lo = _scaled(f["Longitude"])
                if la.shape != a.shape:
                    return None
                step = 8
                sub = (la[::step, ::step] - lat) ** 2 + (lo[::step, ::step] - lon) ** 2
                yi, xi = np.unravel_index(np.nanargmin(sub), sub.shape)
                y0, x0 = int(yi) * step, int(xi) * step
                y1, x1 = min(a.shape[0], y0 + step), min(a.shape[1], x0 + step)
                patch_lat = la[y0:y1, x0:x1]
                patch_lon = lo[y0:y1, x0:x1]
                d = (patch_lat - lat) ** 2 + (patch_lon - lon) ** 2
                py, px = np.unravel_index(np.nanargmin(d), d.shape)
                v = float(a[y0 + int(py), x0 + int(px)])
            else:
                h, w = a.shape[-2], a.shape[-1]
                west, east, south, north = 40.0, 110.0, -10.0, 45.0
                fx = (lon - west) / (east - west)
                fy = (north - lat) / (north - south)
                xi = int(max(0, min(w - 1, round(fx * (w - 1)))))
                yi = int(max(0, min(h - 1, round(fy * (h - 1)))))
                v = float(a[yi, xi])
            if v != v or v < 0 or v > 200:
                return 0.0 if v != v or v < 0 else None
            return v
    except Exception:
        return None


def hem_knot(lat: float, lon: float) -> dict[str, Any] | None:
    """Sample cached HEM/HDF5 or last JSON sidecar. Never invent a rate."""
    ARCHIVE.mkdir(parents=True, exist_ok=True)
    side = ARCHIVE / "last_hem.json"
    if side.exists():
        try:
            blob = json.loads(side.read_text(encoding="utf-8"))
            if blob.get("mm_h") is not None:
                blat = float(blob.get("lat") or 0)
                blon = float(blob.get("lon") or 0)
                if abs(blat - lat) < 0.15 and abs(blon - lon) < 0.15:
                    return {
                        "t": blob.get("t"),
                        "mm_h": float(blob["mm_h"]),
                        "source": "insat-hem-cache",
                        "path": blob.get("path"),
                    }
        except (OSError, json.JSONDecodeError, TypeError, ValueError):
            pass
    files = sorted(
        [p for p in ARCHIVE.rglob("*") if p.is_file() and p.suffix.lower() in {".h5", ".hdf5", ".he5"}],
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    for p in files[:4]:
        v = _sample_h5(p, lat, lon)
        if v is None:
            continue
        pack = {"t": None, "mm_h": v, "source": "insat-hem-h5", "path": str(p)}
        try:
            side.write_text(json.dumps({**pack, "lat": lat, "lon": lon}), encoding="utf-8")
        except OSError:
            pass
        return pack
    return None


def write_mdapi_config() -> Path:
    s = get_settings()
    cfg = {
        "user_credentials": {"username": s.mosdac_user or "", "password": ""},
        "search_parameters": {
            "datasetId": "3SIMG_L1B_STD",
            "startTime": date.today().isoformat(),
            "endTime": date.today().isoformat(),
            "count": "5",
            "boundingBox": "68.0,6.5,97.5,37.0",
            "gId": "",
        },
        "download_settings": {
            "download_path": str(ARCHIVE),
            "organize_by_date": False,
            "skip_user_prompt": True,
            "skip_user_input": True,
        },
    }
    ARCHIVE.mkdir(parents=True, exist_ok=True)
    p = ARCHIVE / "config.json"
    p.write_text(json.dumps(cfg, indent=2), encoding="utf-8")
    return p

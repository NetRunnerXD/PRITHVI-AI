"""MOSDAC mdapi client: search + token download. Credentials from env."""

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

# INSAT-3DS / 3D / 3DR imager L1B, then HEM rainfall.
DATASETS = ("3SIMG_L1B_STD", "3DIMG_L1B_STD", "3RIMG_L1B_STD", "3DIMG_L2B_HEM")


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
        return {"ok": True, "path": str(dest), "bytes": dest.stat().st_size, "cached": True}
    r = await client().get(
        DOWNLOAD_URL,
        params={"id": record_id},
        headers={"Authorization": f"Bearer {tok['access_token']}"},
        timeout=120.0,
    )
    if r.status_code >= 400:
        return {"ok": False, "status": f"http_{r.status_code}", "error": (r.text or "")[:180]}
    dest.write_bytes(r.content)
    return {"ok": True, "path": str(dest), "bytes": dest.stat().st_size, "cached": False}


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


async def download_product(product: str = "3SIMG_L1B_STD") -> dict[str, Any]:
    pack = await search(product, count=1)
    granules = pack.get("granules") or []
    if not granules or not granules[0].get("id"):
        return {"ok": False, "status": "no_granule", **pack, **status()}
    g = granules[0]
    dl = await download_granule(str(g["id"]), g.get("identifier"))
    return {**dl, "granule": g, "search": pack}


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
        },
    }
    ARCHIVE.mkdir(parents=True, exist_ok=True)
    p = ARCHIVE / "config.json"
    p.write_text(json.dumps(cfg, indent=2), encoding="utf-8")
    return p

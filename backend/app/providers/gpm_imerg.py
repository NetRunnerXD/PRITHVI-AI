"""GPM IMERG 30-min 0.1° — GIBS always; GES DISC HDF/OPeNDAP when Earthdata token is set."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from app import cache
from app.config import ROOT, get_settings

ARCHIVE = ROOT / ".cache" / "imerg"
CMR = "https://cmr.earthdata.nasa.gov/search/granules.json"


def earthdata_token() -> str | None:
    s = get_settings()
    t = (s.nasa_earthdata_api or "").strip()
    return t or None


def earthdata_ready() -> bool:
    s = get_settings()
    return bool(earthdata_token() or (s.nasa_earthdata_user and s.nasa_earthdata_pass))


def status() -> dict[str, Any]:
    n = len(list(ARCHIVE.glob("*"))) if ARCHIVE.exists() else 0
    tok = bool(earthdata_token())
    return {
        "wired": True,
        "live": "nasa-gibs-imerg",
        "ges_disc": earthdata_ready(),
        "cmr": True,
        "token": tok,
        "archive_files": n,
        "temporal": "30-min",
        "spatial": "0.1°",
        "api_needed": None
        if earthdata_ready()
        else {
            "env": ["NASA_EARTHDATA_API"],
            "prompt": "Set NASA_EARTHDATA_API to an Earthdata user token from https://urs.earthdata.nasa.gov/documentation/for_users/user_token (or NASA_EARTHDATA_USER + NASA_EARTHDATA_PASS).",
        },
    }


def _headers() -> dict[str, str]:
    tok = earthdata_token()
    if tok:
        return {"Authorization": f"Bearer {tok}"}
    return {}


async def _cmr_latest() -> dict[str, Any] | None:
    hit = cache.get("imerg:cmr")
    if isinstance(hit, dict):
        return hit
    from app.providers.http import client

    r = await client().get(
        CMR,
        params={
            "short_name": "GPM_3IMERGHHE",
            "version": "07",
            "page_size": 1,
            "sort_key": "-start_date",
        },
        headers={"Accept": "application/json"},
    )
    if r.status_code >= 400:
        return None
    body = r.json()
    entries = ((body.get("feed") or {}).get("entry") or [])
    if not entries:
        return None
    e = entries[0]
    raw_links = [lk for lk in (e.get("links") or []) if isinstance(lk, dict)]
    hrefs = [lk.get("href") for lk in raw_links if lk.get("href")]
    href = next((h for h in hrefs if str(h).endswith(".HDF5")), None) or next((h for h in hrefs if h), None)
    opendap = next((h for h in hrefs if h and "opendap" in h.lower()), None)
    pack = {
        "id": e.get("id"),
        "title": e.get("title"),
        "time_start": e.get("time_start"),
        "href": href,
        "opendap": opendap,
        "n_links": len(hrefs),
    }
    cache.set("imerg:cmr", pack, 900)
    return pack


async def _opendap_point(lat: float, lon: float) -> dict[str, Any] | None:
    """GDS ASCII last precip at the pin. Auth via Bearer when token present."""
    from app.providers.http import client

    # 0.1° grid: lon -179.95 + i*0.1, lat -89.95 + j*0.1
    li = int(round((lon + 179.95) / 0.1))
    lj = int(round((lat + 89.95) / 0.1))
    li = max(0, min(3599, li))
    lj = max(0, min(1799, lj))
    cmr = await _cmr_latest()
    urls = []
    if cmr and cmr.get("opendap"):
        base = str(cmr["opendap"]).rstrip("/")
        urls.append(f"{base}.ascii?Grid/precipitation[0:0][{lj}:1:{lj}][{li}:1:{li}]")
        urls.append(f"{base}.ascii?precipitation[0:0][{lj}][{li}]")
    urls.append(f"https://gpm1.gesdisc.eosdis.nasa.gov/dods/GPM_3IMERGHHE_07.ascii?precip[0:1:0][{lj}:1:{lj}][{li}:1:{li}]")
    last: dict[str, Any] = {"ok": False, "status": "empty"}
    for url in urls:
        try:
            r = await client().get(url, headers=_headers(), timeout=40.0)
        except Exception as e:
            last = {"ok": False, "status": "error", "error": str(e)[:160]}
            continue
        if r.status_code >= 400:
            last = {"ok": False, "status": f"http_{r.status_code}", "error": (r.text or "")[:120], "url_kind": "opendap"}
            continue
        text = r.text
        nums = []
        for tok in text.replace(",", " ").split():
            try:
                nums.append(float(tok))
            except ValueError:
                continue
        mmh = None
        for v in reversed(nums):
            if -1 < v < 200 and v != -9999.9:
                mmh = v
                break
        if mmh is not None:
            return {"ok": True, "mm_h": mmh, "source": "gesdisc-opendap-GPM_3IMERGHHE", "lat_i": lj, "lon_i": li}
        last = {"ok": False, "status": "no_value"}
    return last


async def fetch_pin(lat: float, lon: float) -> dict[str, Any]:
    from app.providers import gibs_ir

    live = await gibs_ir.fetch_imerg(lat, lon)
    st = status()
    cmr = None
    ges = None
    if earthdata_ready():
        try:
            cmr = await _cmr_latest()
        except Exception:
            cmr = None
        try:
            ges = await _opendap_point(lat, lon)
        except Exception as e:
            ges = {"ok": False, "error": str(e)[:160]}
    mmh = (ges or {}).get("mm_h") if (ges or {}).get("ok") else live.get("mm_h")
    ARCHIVE.mkdir(parents=True, exist_ok=True)
    try:
        (ARCHIVE / "last.json").write_text(
            json.dumps(
                {
                    "lat": lat,
                    "lon": lon,
                    "mm_h": mmh,
                    "gibs_ok": live.get("ok"),
                    "ges_ok": (ges or {}).get("ok"),
                    "cmr": (cmr or {}).get("title"),
                    "t": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                }
            ),
            encoding="utf-8",
        )
    except OSError:
        pass
    return {
        **live,
        **st,
        "mm_h": mmh,
        "ok": bool(live.get("ok") or (ges or {}).get("ok")),
        "ges_disc": ges,
        "cmr": cmr,
        "source": (ges or {}).get("source") if (ges or {}).get("ok") else live.get("source"),
    }

"""GPM IMERG 30-min 0.1° — GIBS always; GES DISC HDF/OPeNDAP when Earthdata token is set."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from app import cache
from app.config import ROOT, get_settings

ARCHIVE = ROOT / ".cache" / "imerg"
CMR = "https://cmr.earthdata.nasa.gov/search/granules.json"
OBS_LOG = ROOT / ".cache" / "imerg" / "obs_log.jsonl"


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
        "gesdisc_eula": GESDISC_EULA,
        "note": "GES DISC HDF/OPeNDAP needs the Earthdata token plus one-time GES DISC EULA approval.",
    }


GESDISC_EULA = "https://urs.earthdata.nasa.gov/approve_app?client_id=e2WVk8Pw6weeLUKZYOxvTQ"


def _headers() -> dict[str, str]:
    tok = earthdata_token()
    h = {"Accept": "*/*"}
    if tok:
        h["Authorization"] = f"Bearer {tok}"
    return h


def _eula_from_body(status_code: int, text: str) -> str | None:
    if status_code != 403:
        return None
    if "EULA" in (text or "") or "approve_app" in (text or ""):
        return GESDISC_EULA
    return None


async def _cmr_latest(short_name: str = "GPM_3IMERGHHE") -> dict[str, Any] | None:
    ck = f"imerg:cmr:{short_name}"
    hit = cache.get(ck)
    if isinstance(hit, dict):
        return hit
    from app.providers.http import client

    r = await client().get(
        CMR,
        params={
            "short_name": short_name,
            "version": "07",
            "page_size": 1,
            "sort_key": "-start_date",
        },
        headers={**_headers(), "Accept": "application/json"},
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
    cache.set(ck, pack, 900)
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
        urls.append(f"{base}.ascii?precipitationCal[0:0][{lj}:1:{lj}][{li}:1:{li}]")
        urls.append(f"{base}.ascii?Grid/precipitationCal[0:0][{lj}:1:{lj}][{li}:1:{li}]")
        urls.append(f"{base}.ascii?Grid/precipitation[0:0][{lj}:1:{lj}][{li}:1:{li}]")
        urls.append(f"{base}.ascii?precipitation[0:0][{lj}][{li}]")
    last: dict[str, Any] = {"ok": False, "status": "empty"}
    for url in urls:
        try:
            r = await client().get(url, headers=_headers(), timeout=40.0)
        except Exception as e:
            last = {"ok": False, "status": "error", "error": str(e)[:160]}
            continue
        if r.status_code >= 400:
            eula = _eula_from_body(r.status_code, r.text or "")
            last = {
                "ok": False,
                "status": f"http_{r.status_code}",
                "error": (r.text or "")[:120],
                "url_kind": "opendap",
                "eula": eula,
            }
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


async def _hdf_point(
    lat: float, lon: float, cmr: dict[str, Any] | None, *, download: bool = True
) -> dict[str, Any] | None:
    """Sample IMERG HDF5 at the pin. Live snapshot must not download granules."""
    ARCHIVE.mkdir(parents=True, exist_ok=True)
    name = str((cmr or {}).get("title") or "").split(":")[-1]
    dest = ARCHIVE / name if name else None
    if dest is None or not dest.exists() or dest.stat().st_size < 1024:
        existing = sorted(ARCHIVE.glob("*.HDF5"), key=lambda p: p.stat().st_mtime, reverse=True)
        dest = existing[0] if existing else dest
    if dest is None or not dest.exists() or dest.stat().st_size < 1024:
        if not download or not cmr or not cmr.get("href"):
            return None
        from app.providers.http import client

        name = str(cmr.get("title") or "imerg").split(":")[-1]
        dest = ARCHIVE / name
        r = await client().get(cmr["href"], headers=_headers(), timeout=120.0)
        if r.status_code >= 400:
            return {
                "ok": False,
                "status": f"http_{r.status_code}",
                "eula": _eula_from_body(r.status_code, r.text or ""),
                "url_kind": "hdf5",
            }
        dest.write_bytes(r.content)
    try:
        import h5py
        import numpy as np
    except ImportError:
        return {"ok": False, "status": "h5py_missing"}
    li = int(round((lon + 179.95) / 0.1))
    lj = int(round((lat + 89.95) / 0.1))
    li = max(0, min(3599, li))
    lj = max(0, min(1799, lj))
    try:
        with h5py.File(dest, "r") as f:
            ds = None
            for key in ("precipitationCal", "precipitation", "/Grid/precipitationCal", "/Grid/precipitation"):
                if key in f:
                    ds = f[key]
                    break
            if ds is None and "Grid" in f:
                g = f["Grid"]
                for key in ("precipitationCal", "precipitation"):
                    if key in g:
                        ds = g[key]
                        break
            if ds is None:
                return {"ok": False, "status": "no_precip_dataset"}
            a = np.array(ds[()])
            while a.ndim > 2:
                a = a[0]
            # IMERG often lon,lat
            if a.shape[0] == 3600 and a.shape[1] == 1800:
                v = float(a[li, lj])
            elif a.shape[0] == 1800 and a.shape[1] == 3600:
                v = float(a[lj, li])
            else:
                v = float(a.flat[min(len(a.flat) - 1, lj * a.shape[-1] + li)])
            if v != v or v < 0:
                v = 0.0
            return {"ok": True, "mm_h": v, "source": "gesdisc-hdf5-GPM_3IMERGHHE", "path": str(dest)}
    except Exception as e:
        return {"ok": False, "status": "hdf_error", "error": str(e)[:160]}


async def fetch_pin(lat: float, lon: float, *, heavy: bool = False) -> dict[str, Any]:
    """Live path: GIBS + cached HDF only. heavy=True downloads the latest granule (nightly/verify)."""
    from app.providers import gibs_ir

    live = await gibs_ir.fetch_imerg(lat, lon)
    st = status()
    cmr = None
    ges = None
    if earthdata_ready() and heavy:
        try:
            cmr = await _cmr_latest()
        except Exception:
            cmr = None
        try:
            ges = await _opendap_point(lat, lon)
        except Exception as e:
            ges = {"ok": False, "error": str(e)[:160]}
    if heavy and not (ges or {}).get("ok"):
        try:
            hdf = await _hdf_point(lat, lon, cmr, download=True)
        except Exception as e:
            hdf = {"ok": False, "error": str(e)[:160]}
        if hdf and hdf.get("ok"):
            ges = hdf
        elif hdf and hdf.get("eula"):
            ges = {**(ges or {}), **hdf}
    mmh = (ges or {}).get("mm_h") if (ges or {}).get("ok") else live.get("mm_h")
    append_obs(lat, lon, mmh, "gpm-imerg")
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


def append_obs(lat: float, lon: float, mm_h: float | None, source: str) -> None:
    if mm_h is None:
        return
    ARCHIVE.mkdir(parents=True, exist_ok=True)
    OBS_LOG.parent.mkdir(parents=True, exist_ok=True)
    row = {
        "lat": round(lat, 4),
        "lon": round(lon, 4),
        "mm_h": float(mm_h),
        "source": source,
        "t": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    try:
        with OBS_LOG.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(row) + "\n")
    except OSError:
        pass


async def fetch_late_pin(lat: float, lon: float) -> dict[str, Any]:
    """IMERG Late (GPM_3IMERGHHL) for verification labels. Not a live 15-min nowcast."""
    st = status()
    cmr = None
    if earthdata_ready():
        try:
            cmr = await _cmr_latest("GPM_3IMERGHHL")
        except Exception as e:
            cmr = {"ok": False, "error": str(e)[:160]}
    live = await fetch_pin(lat, lon, heavy=True)
    mmh = live.get("mm_h")
    append_obs(lat, lon, mmh, str(live.get("source") or "imerg"))
    return {
        **st,
        "ok": bool(live.get("ok") or (cmr and cmr.get("href"))),
        "mm_h": mmh,
        "cmr_late": cmr,
        "live": live,
        "source": "gpm-imerg-late" if cmr else live.get("source"),
        "note": "Late/Final are labels. Early/GIBS may still be the live rate.",
    }

"""Live GFS + ECMWF IFS inputs for PRITHVI-Nowcast v7, built exactly like the research bundle
(PRITHVI-AI-Research gpu_bundle/v7/build_dataset_v7.py; raw fields as fetch_gfs.py,
fetch_nwp_v7.py and v6/fetch_ifs_archive.py: India crop 133x141 @0.25°, lat 38→5 N, lon 65→100 E,
stored float16).

Latency rule (binding, same as training): for issue time t
  GFS run = newest 6-hourly init ≤ t−6 h (fallback t−12 h), IFS run = newest 00/12 init ≤ t−8 h
  (fallback 12 h older). Nothing newer is ever used, even if it is already published.

Sources: GFS — NOMADS grib filter (regional subset, ~5–40 KB per file), AWS open bucket
byte-range as fallback. IFS — ECMWF open data (data.ecmwf.int, then Google/AWS mirrors),
byte-range of single fields from the .index (global field, cropped right after decoding).
Real data only: a group whose fields are missing is returned with mask 0.
"""

from __future__ import annotations

import asyncio
import json
import re
import struct
from datetime import datetime, timedelta
from typing import Any, Awaitable, Callable

import numpy as np

from app import cache

NOMADS = "https://nomads.ncep.noaa.gov/cgi-bin/filter_gfs_0p25.pl"
GFS_AWS = "https://noaa-gfs-bdp-pds.s3.amazonaws.com"
IFS_MIRRORS = ["https://data.ecmwf.int/forecasts", "https://storage.googleapis.com/ecmwf-open-data", "https://ecmwf-forecasts.s3.eu-central-1.amazonaws.com"]
GLA, GLO = slice(208, 341), slice(260, 401)  # GFS 0.25 global (lat 90..-90, lon 0..359.75) → India crop
ILA, ILO = slice(208, 341), slice(980, 1121)  # IFS open data (lat 90..-90, lon -180..179.75)
# bundle coarse grid (80x87) = 4x4 means of the IMERG 0.1° India grid; nearest 0.25° NWP cell
_LAT = -89.95 + 0.1 * np.arange(949, 949 + 320)
_LON = -179.95 + 0.1 * np.arange(2449, 2449 + 348)
LAT4, LON4 = _LAT.reshape(80, 4).mean(1), _LON.reshape(87, 4).mean(1)
GI = np.clip(np.round((38 - LAT4) / 0.25).astype(int), 0, 132)
GJ = np.clip(np.round((LON4 - 65) / 0.25).astype(int), 0, 140)
# GFS: f000 env (fetch_gfs.py) + APCP buckets (fetch_gfs.py / GFS_EXTRA / fetch_nwp_v7.py)
GFS_ENV = [("CAPE", "surface"), ("CIN", "surface"), ("PWAT", "entire atmosphere"), ("RH", "850 mb"), ("UGRD", "850 mb"), ("VGRD", "850 mb")]
GFS_APCP = {3: "0-3", 6: "0-6", 9: "6-9", 12: "6-12", 15: "12-15", 18: "12-18", 21: "18-21", 24: "18-24"}
# IFS: tp steps present in training (ifs_v6: 12..36 by 6; tp3: 6,9,15,21,27,33); env at step 24
IFS_TP_STEPS = [6, 9, 12, 15, 18, 21, 24, 27, 30, 33, 36]
IFS_ENV_STEP = 24
IFS_ENV = [("mucape", "sfc", None), ("tcwv", "sfc", None), ("r", "pl", "850"), ("u", "pl", "850"), ("v", "pl", "850"), ("d", "pl", "850")]
IFS_ENV_200 = [("u", "pl", "200"), ("v", "pl", "200")]  # PN-Correct shear (fetch_ifs_archive.py ENV)
IFS_V6_STEPS = [12, 18, 24, 30, 36]  # tp steps of the ifs_v6 archive (PN-Correct reads only these)
Fetch = Callable[[str, "tuple[int, int] | None"], Awaitable["bytes | None"]]


# ---------------------------------------------------------------- HTTP + GRIB helpers
async def _http_get(url: str, rng: tuple[int, int] | None = None) -> bytes | None:
    from app.providers.http import client

    h = {"Range": f"bytes={rng[0]}-{rng[1]}"} if rng else {}
    r = await client().get(url, headers=h, timeout=60.0)
    if r.status_code == 404:
        return None
    if r.status_code >= 400:
        raise RuntimeError(f"http_{r.status_code}")
    return r.content


def split_grib(blob: bytes) -> list[bytes]:
    """Split a concatenation of GRIB2 messages (length = uint64 at bytes 8..16)."""
    out, k = [], 0
    while True:
        k = blob.find(b"GRIB", k)
        if k < 0 or k + 16 > len(blob):
            return out
        n = struct.unpack(">Q", blob[k + 8:k + 16])[0] if blob[k + 7] == 2 else struct.unpack(">I", b"\0" + blob[k + 4:k + 7])[0]
        out.append(blob[k:k + n]); k += max(n, 4)


def _decode(msg: bytes) -> tuple[dict[str, Any], np.ndarray]:
    import eccodes

    h = eccodes.codes_new_from_message(msg)
    try:
        keys = {}
        for k in ("shortName", "typeOfFirstFixedSurface", "level", "startStep", "endStep", "Ni", "Nj", "latitudeOfFirstGridPointInDegrees", "longitudeOfFirstGridPointInDegrees"):
            try:
                keys[k] = eccodes.codes_get(h, k)
            except Exception:  # noqa: BLE001
                keys[k] = None
        v = np.asarray(eccodes.codes_get_values(h), np.float64).reshape(int(keys["Nj"]), int(keys["Ni"]))
        return keys, v
    finally:
        eccodes.codes_release(h)


def _crop_global(v: np.ndarray, la: slice, lo: slice) -> np.ndarray:
    assert v.shape == (721, 1440), v.shape
    return v[la, lo].astype(np.float32)


# ---------------------------------------------------------------- latency-respecting run choice (verbatim)
def runs_gfs(t: datetime) -> list[datetime]:
    r = t - timedelta(hours=6); r = r.replace(hour=r.hour // 6 * 6); return [r, r - timedelta(hours=6)]


def runs_ifs(t: datetime) -> list[datetime]:
    r = t - timedelta(hours=8); r = r.replace(hour=r.hour // 12 * 12); return [r, r - timedelta(hours=12)]


# ---------------------------------------------------------------- GFS fetch
def _gfs_key(keys: dict[str, Any]) -> str | None:
    sn, tf, lv = keys.get("shortName"), keys.get("typeOfFirstFixedSurface"), keys.get("level")
    if sn == "tp" and tf == 1:
        return f"APCP_{keys.get('startStep')}-{keys.get('endStep')}"
    m = {("cape", 1): "CAPE", ("cin", 1): "CIN", ("pwat", 200): "PWAT", ("pwat", 10): "PWAT"}.get((sn, tf))
    if m:
        return m
    if tf == 100 and int(lv or 0) == 850:
        return {"r": "RH", "u": "UGRD", "v": "VGRD"}.get(sn)
    return None


async def _gfs_file_nomads(r: datetime, f: int, get: Fetch) -> dict[str, np.ndarray] | None:
    if f == 0:
        q = "&".join(["var_CAPE=on", "var_CIN=on", "var_PWAT=on", "var_RH=on", "var_UGRD=on", "var_VGRD=on", "lev_surface=on", "lev_entire_atmosphere=on", "lev_850_mb=on"])
    else:
        q = "var_APCP=on&lev_surface=on"
    url = (f"{NOMADS}?dir=%2Fgfs.{r:%Y%m%d}%2F{r:%H}%2Fatmos&file=gfs.t{r:%H}z.pgrb2.0p25.f{f:03d}&{q}"
           "&subregion=&toplat=38&leftlon=65&rightlon=100&bottomlat=5")
    blob = await get(url, None)
    if not blob or not blob.startswith(b"GRIB"):
        return None
    out: dict[str, np.ndarray] = {}
    for msg in split_grib(blob):
        keys, v = _decode(msg)
        k = _gfs_key(keys)
        if k is None or k in out:
            continue
        if v.shape != (133, 141) or abs(float(keys["latitudeOfFirstGridPointInDegrees"]) - 38.0) > 1e-6 or abs(float(keys["longitudeOfFirstGridPointInDegrees"]) - 65.0) > 1e-6:
            return None  # unexpected subset grid → let the byte-range path handle it
        out[k] = v.astype(np.float32)
    return out


async def _gfs_file_aws(r: datetime, f: int, get: Fetch) -> dict[str, np.ndarray] | None:
    u = f"{GFS_AWS}/gfs.{r:%Y%m%d}/{r:%H}/atmos/gfs.t{r:%H}z.pgrb2.0p25.f{f:03d}"
    idx = await get(u + ".idx", None)
    if not idx:
        return None
    L = idx.decode().strip().split("\n")
    want = GFS_ENV if f == 0 else [("APCP", "surface:" + GFS_APCP[f] + " hour acc")]
    out: dict[str, np.ndarray] = {}
    for v_, lev in want:
        for j, ln in enumerate(L):
            p = ln.split(":")
            if len(p) > 4 and p[3] == v_ and ":".join(p[4:]).startswith(lev):
                s = int(p[1]); e = int(L[j + 1].split(":")[1]) - 1 if j + 1 < len(L) else s + 3_000_000
                g = await get(u, (s, e))
                if g:
                    keys, v = _decode(g)
                    k = v_ if f == 0 else f"APCP_{GFS_APCP[f]}"
                    out[k] = _crop_global(v, GLA, GLO)
                break
    return out


async def gfs_run(r: datetime, steps: list[int], get: Fetch | None = None) -> dict[str, np.ndarray]:
    """Training-format dict for one GFS run: CAPE_f000.., APCP_fNNN (bucket of that file), float16→32."""
    get = get or _http_get
    ck = f"pn7:gfs:{r:%Y%m%d%H}"
    have: dict[str, np.ndarray] = dict(cache.get(ck) or {})
    for f in steps:
        need = [f"{v}_f000" for v, _ in GFS_ENV] if f == 0 else [f"APCP_f{f:03d}"]
        if all(k in have for k in need):
            continue
        want = [v for v, _ in GFS_ENV] if f == 0 else [f"APCP_{GFS_APCP[f]}"]
        got: dict[str, np.ndarray] = {}
        for src in (_gfs_file_nomads, _gfs_file_aws, _gfs_file_nomads, _gfs_file_aws):  # one retry each
            try:
                part = await src(r, f, get) or {}
            except Exception:  # noqa: BLE001
                part = {}
            got.update({k: v for k, v in part.items() if k not in got})
            if all(k in got for k in want):  # a partial NOMADS reply (rate limit) falls through to AWS
                break
        if not got:
            continue
        if f == 0:
            for v, _ in GFS_ENV:
                if v in got:
                    have[f"{v}_f000"] = got[v].astype(np.float16).astype(np.float32)
        else:
            b = got.get(f"APCP_{GFS_APCP[f]}")
            if b is not None:
                have[f"APCP_f{f:03d}"] = b.astype(np.float16).astype(np.float32)
    cache.set(ck, have, 30 * 3600)
    return have


# ---------------------------------------------------------------- IFS fetch
async def ifs_run(r: datetime, steps: list[int], with_env: bool, get: Fetch | None = None, with_200: bool = False) -> dict[str, np.ndarray]:
    get = get or _http_get
    ck = f"pn7:ifs:{r:%Y%m%d%H}"
    have: dict[str, np.ndarray] = dict(cache.get(ck) or {})
    todo: dict[int, list[tuple[str, str, str, str | None]]] = {}
    for st in steps:
        if f"tp_{st:03d}" not in have:
            todo.setdefault(st, []).append((f"tp_{st:03d}", "tp", "sfc", None))
    if with_env:
        for p, lt, lv in IFS_ENV + (IFS_ENV_200 if with_200 else []):
            k = f"{p}{lv or ''}"
            if k not in have:
                todo.setdefault(IFS_ENV_STEP, []).append((k, p, lt, lv))
    for st, want in todo.items():
        for m in IFS_MIRRORS:
            stem = f"{m}/{r:%Y%m%d}/{r:%H}z/ifs/0p25/oper/{r:%Y%m%d%H}0000-{st}h-oper-fc"
            try:
                ix = await get(stem + ".index", None)
            except Exception:  # noqa: BLE001
                ix = None
            if not ix:
                continue
            idx = [json.loads(line) for line in ix.decode("utf-8-sig").splitlines() if line.strip()]
            ok = False
            for key, p, lt, lv in want:
                j = [x for x in idx if x.get("param") == p and x.get("levtype") == lt and (lv is None or x.get("levelist") == lv)]
                if not j:
                    continue
                try:
                    g = await get(stem + ".grib2", (j[0]["_offset"], j[0]["_offset"] + j[0]["_length"] - 1))
                except Exception:  # noqa: BLE001
                    g = None
                if not g:
                    continue
                keys, v = _decode(g)
                if v.shape != (721, 1440) or keys.get("longitudeOfFirstGridPointInDegrees") not in (180.0, -180.0):
                    continue
                a = _crop_global(v, ILA, ILO) * (1000 if key.startswith("tp") else 1e5 if key == "d850" else 1)
                have[key] = a.astype(np.float16).astype(np.float32); ok = True
            if ok:
                break
    cache.set(ck, have, 30 * 3600)
    return have


# ---------------------------------------------------------------- verbatim bundle maths (build_dataset_v7.py)
def gfs_cum(z: dict[str, np.ndarray]):
    if "APCP_f006" not in z:
        return None
    g = lambda k: np.maximum(z[k].astype(np.float32), 0)  # noqa: E731
    C = {0: 0.0, 6: g("APCP_f006")}
    if "APCP_f003" in z: C[3] = g("APCP_f003")
    if "APCP_f012" in z:
        C[12] = C[6] + g("APCP_f012")
        if "APCP_f009" in z: C[9] = C[6] + g("APCP_f009")
        if "APCP_f018" in z:
            C[18] = C[12] + g("APCP_f018")
            if "APCP_f015" in z: C[15] = C[12] + g("APCP_f015")
            if "APCP_f024" in z:
                C[24] = C[18] + g("APCP_f024")
                if "APCP_f021" in z: C[21] = C[18] + g("APCP_f021")
    return C


def ifs_cum(z: dict[str, np.ndarray]):
    C: dict[int, Any] = {0: 0.0}
    for k, v in z.items():
        m = re.fullmatch(r"tp_(\d{3})", k)
        if m: C[int(m[1])] = np.maximum(v.astype(np.float32), 0)
    return C if len(C) > 1 else None


def rate(C, s):
    lo = max([k for k in C if k <= s], default=None); hi = min([k for k in C if k > s], default=None)
    if lo is None or hi is None or hi - lo > 6: return None
    return np.maximum(C[hi] - C[lo], 0) / (hi - lo)


def windows(t: datetime, kind: str, runs: dict[datetime, dict[str, np.ndarray]]):
    out: list[Any] = [None] * 4; age = None; used: list[datetime] = []
    for r in (runs_gfs(t) if kind == "gfs" else runs_ifs(t)):
        z = runs.get(r) or {}
        C = gfs_cum(z) if kind == "gfs" else ifs_cum(z)
        if C is None: continue
        for k in range(4):
            if out[k] is not None: continue
            hs = [rate(C, (t - r).total_seconds() / 3600 + 3 * k + j + 0.5) for j in range(3)]
            if all(h is not None for h in hs):
                out[k] = (sum(hs) / 3)[GI][:, GJ]; age = age or (t - r).total_seconds() / 3600
                if r not in used: used.append(r)
    return (out if all(o is not None for o in out) else None), age, used


def q8(a):
    return np.clip(np.round(np.log1p(np.maximum(a, 0)) / 0.02), 0, 255).astype(np.uint8)


def zq(x, mu, sd):
    return np.clip(np.round((x - mu) / sd * 32 + 128), 0, 255).astype(np.uint8)


def _steps_needed(age_h: float, avail: list[int]) -> list[int]:
    S = sorted(set([0] + avail)); need = set()
    for j in range(12):
        s = age_h + j + 0.5
        lo = max([k for k in S if k <= s], default=None); hi = min([k for k in S if k > s], default=None)
        if lo is not None: need.add(lo)
        if hi is not None: need.add(hi)
    return sorted(k for k in need if k > 0)


async def build(t: datetime, norm: dict[str, list[float]], get: Fetch | None = None) -> dict[str, Any]:
    """Model NWP inputs for issue time t (naive UTC hour): nrate [8,80,87] (log1p mm/h, u8-quantised),
    nm [2], env [12,80,87] ((u8-128)/32), em [2], ages [2] (h), plus provenance."""
    gfs_runs: dict[datetime, dict] = {}; ifs_runs: dict[datetime, dict] = {}
    g0, i0 = runs_gfs(t)[0], runs_ifs(t)[0]
    gsteps = [0] + sorted(GFS_APCP)  # GFS buckets chain (f012 = 6-12 h needs f006): fetch all; ~5–40 KB each via NOMADS
    isteps = _steps_needed((t - i0).total_seconds() / 3600, IFS_TP_STEPS)
    errs: list[str] = []

    async def _g(r, st):
        try: gfs_runs[r] = await gfs_run(r, st, get)
        except Exception as e: errs.append(f"gfs {r:%Y%m%d%H}: {str(e)[:60]}")  # noqa: E701
    async def _i(r, st, env):
        try: ifs_runs[r] = await ifs_run(r, st, env, get)
        except Exception as e: errs.append(f"ifs {r:%Y%m%d%H}: {str(e)[:60]}")  # noqa: E701

    await asyncio.gather(_g(g0, gsteps), _i(i0, isteps, True))
    nrate = np.zeros((8, 80, 87), np.uint8); nm = np.zeros(2, np.float32); age = np.zeros(2, np.float32); used: dict[str, list[str]] = {}
    for m, (kind, runs, fb) in enumerate((("gfs", gfs_runs, runs_gfs(t)[1]), ("ifs", ifs_runs, runs_ifs(t)[1]))):
        w, a, u = windows(t, kind, runs)
        if w is None:  # fallback run (12 h older for IFS, 6 h for GFS), fetched only when needed
            ag = (t - fb).total_seconds() / 3600
            if kind == "gfs": await _g(fb, sorted(GFS_APCP))
            else: await _i(fb, _steps_needed(ag, IFS_TP_STEPS), False)
            w, a, u = windows(t, kind, gfs_runs if kind == "gfs" else ifs_runs)
        if w is not None:
            nrate[4 * m:4 * m + 4] = q8(np.stack(w)); nm[m] = 1.0; age[m] = a
        used[kind] = [f"{r:%Y-%m-%dT%H}Z" for r in u]
    envt = np.zeros((12, 80, 87), np.float32); em = np.zeros(2, np.float32)
    zg = gfs_runs.get(g0) or {}
    if all(k in zg for k in ("CAPE_f000", "CIN_f000", "PWAT_f000", "RH_f000", "UGRD_f000", "VGRD_f000")):
        f = lambda k: zg[k].astype(np.float32)[GI][:, GJ]  # noqa: E731
        envt[:6] = np.stack([np.log1p(np.maximum(f("CAPE_f000"), 0)), -np.abs(f("CIN_f000")), f("PWAT_f000"), f("RH_f000"), f("UGRD_f000"), f("VGRD_f000")]); em[0] = 1
    zi = ifs_runs.get(i0) or {}
    if all(k in zi for k in ("mucape", "tcwv", "r850", "u850", "v850", "d850")):
        f = lambda k: zi[k].astype(np.float32)[GI][:, GJ]  # noqa: E731
        envt[6:] = np.stack([np.log1p(np.maximum(f("mucape"), 0)), f("tcwv"), f("r850"), f("u850"), f("v850"), f("d850")]); em[1] = 1
    envt = envt.astype(np.float16).astype(np.float32)  # bundle staged env as float16
    env = np.zeros((12, 80, 87), np.float32)
    for c in range(12):
        mu, sd = norm[f"nenv{c}"]
        env[c] = (zq(np.nan_to_num(envt[c], nan=mu), mu, sd).astype(np.float32) - 128) / 32
    return {
        "nrate": nrate.astype(np.float32) * 0.02, "nm": nm, "env": env, "em": em, "age_h": age,
        "runs": {"gfs": used.get("gfs") or [], "ifs": used.get("ifs") or [], "gfs_env": f"{g0:%Y-%m-%dT%H}Z" if em[0] else None, "ifs_env": f"{i0:%Y-%m-%dT%H}Z" if em[1] else None},
        "errors": errs[:4],
    }


# ---------------------------------------------------------------- PN-Correct v6 extras (same runs, same latency rule)
def correct_steps_gfs() -> list[int]:
    """f000 env + 6-h APCP buckets f006/f012/f018/f024 (all also in the v7 GFS fetch → cache hits)."""
    return [0, 6, 12, 18, 24]


def correct_steps_ifs(T: datetime) -> list[int]:
    """6-h tp block ends/starts (ifs_v6 steps) covering T+L−0.5 for L = 6, 9, 12."""
    age = (T - runs_ifs(T)[0]).total_seconds() / 3600; out: set[int] = set()
    for L in (6, 9, 12):
        s = age + L - 0.5; b0 = int(s // 6) * 6; out.update(k for k in (b0, b0 + 6) if k)
    return sorted(out)


async def build_correct_runs(T: datetime, get: Fetch | None = None) -> dict[str, Any]:
    """Primary latency-respecting GFS/IFS runs for PN-Correct (no fallback runs, as in the v6 builder),
    with IFS u200/v200 added. Returns the raw training-format dicts (float16-rounded crops)."""
    g0, i0 = runs_gfs(T)[0], runs_ifs(T)[0]
    errs: list[str] = []
    try:
        zg = await gfs_run(g0, correct_steps_gfs(), get)
    except Exception as e:  # noqa: BLE001
        zg = {}; errs.append(f"gfs {g0:%Y%m%d%H}: {str(e)[:60]}")
    try:
        zi = await ifs_run(i0, correct_steps_ifs(T), True, get, with_200=True)
    except Exception as e:  # noqa: BLE001
        zi = {}; errs.append(f"ifs {i0:%Y%m%d%H}: {str(e)[:60]}")
    return {"gfs": zg, "ifs": zi, "gfs_run": g0, "ifs_run": i0, "errors": errs}

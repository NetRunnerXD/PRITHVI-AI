"""NOAA GFS worldwide background for the map's weather layers (NOT highlights).

* Source: NOMADS grib filter (filter_gfs_0p50.pl) — only 8 fields at 4 levels, ~2.2 MB per
  forecast step at 0.5°. Steps f000…f024 every 3 h of the newest COMPLETE cycle (f024 index
  present). Refreshed per cycle (6 h); a cheap HEAD check runs at most every 45 min so a new
  cycle is picked up mid-cycle.
* Decoded with ecCodes (pip `eccodes`, binary wheels); if it is missing the layer reports
  `eccodes_missing` and the map simply shows the India Open-Meteo inset.
* Served as 8-bit greyscale PNGs, 1° (360×161, 80°S–80°N, lon −180…179) per field and step,
  with a JSON meta giving the linear/log de-quantisation — ~10–35 KB per field on the wire.
"""

from __future__ import annotations

import asyncio
import io
import os
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import numpy as np

from app.config import get_settings

UTC = timezone.utc
PROD = "https://nomads.ncep.noaa.gov/pub/data/nccf/com/gfs/prod"
FILTER = "https://nomads.ncep.noaa.gov/cgi-bin/filter_gfs_0p50.pl"
STEPS = list(range(0, 25, 3))
LAT_S, LAT_N = -80.0, 80.0
NX, NY = 360, 161
# key: (min, max, transform) — value = min + q/255·(max−min) on the transformed scale
QUANT: dict[str, tuple[float, float, str]] = {
    "temp_c": (-50.0, 50.0, "lin"),
    "rh_pct": (0.0, 100.0, "lin"),
    "wind_u": (-50.0, 50.0, "lin"),
    "wind_v": (-50.0, 50.0, "lin"),
    "pressure_hpa": (940.0, 1060.0, "lin"),
    "cloud_pct": (0.0, 100.0, "lin"),
    "precip_mm": (0.0, float(np.log1p(100.0)), "log1p"),
    "cape": (0.0, 5000.0, "lin"),
}
_STATE: dict[str, Any] = {"cycle": None, "fields": None, "checked": 0.0, "status": "idle", "error": None, "source": None}
_LOCK = asyncio.Lock()
_TASK: asyncio.Task | None = None


def decode_enabled() -> bool:
    """Local/PC keeps NOMADS GRIB decode. Cloud/Render skips it (Open-Meteo serves the map)."""
    raw = (os.environ.get("GFS_DECODE_ENABLED") or "").strip().lower()
    if raw:
        return raw in {"1", "true", "yes", "on"}
    if (os.environ.get("CLOUD_LIGHT") or "").strip().lower() in {"1", "true", "yes", "on"}:
        return False
    if (os.environ.get("RENDER") or "").strip():
        return False
    return True


def _dir() -> Path:
    p = Path(get_settings().cache_dir) / "gfs"
    p.mkdir(parents=True, exist_ok=True)
    return p


def _cycles(now: datetime | None = None) -> list[datetime]:
    now = now or datetime.now(UTC)
    base = now.replace(hour=now.hour - now.hour % 6, minute=0, second=0, microsecond=0)
    return [base - timedelta(hours=6 * k) for k in range(5)]


async def latest_cycle() -> datetime | None:
    """Newest cycle whose f024 index exists (≈ cycle + 3.5–4.5 h)."""
    from app.providers.http import client

    for c in _cycles():
        url = f"{PROD}/gfs.{c:%Y%m%d}/{c:%H}/atmos/gfs.t{c:%H}z.pgrb2.0p50.f024.idx"
        try:
            r = await client().head(url, timeout=15.0)
        except Exception:  # noqa: BLE001
            continue
        if r.status_code == 200:
            return c
    return None


def _decode(blob: bytes) -> dict[str, np.ndarray]:
    import eccodes

    import tempfile

    out: dict[str, np.ndarray] = {}
    # ecCodes reads messages from a real file handle; use a temp file.

    with tempfile.NamedTemporaryFile(suffix=".grb2", delete=False) as tf:
        tf.write(blob)
        path = tf.name
    try:
        with open(path, "rb") as fh:
            while True:
                g = eccodes.codes_grib_new_from_file(fh)
                if g is None:
                    break
                try:
                    sn = eccodes.codes_get(g, "shortName")
                    lvl = eccodes.codes_get(g, "typeOfLevel")
                    st = eccodes.codes_get(g, "stepType")
                    ni, nj = eccodes.codes_get(g, "Ni"), eccodes.codes_get(g, "Nj")
                    if st not in ("instant",):
                        continue
                    key = {
                        ("2t", "heightAboveGround"): "temp_c",
                        ("2r", "heightAboveGround"): "rh_pct",
                        ("10u", "heightAboveGround"): "wind_u",
                        ("10v", "heightAboveGround"): "wind_v",
                        ("prmsl", "meanSea"): "pressure_hpa",
                        ("tcc", "atmosphere"): "cloud_pct",
                        ("prate", "surface"): "precip_mm",
                        ("cape", "surface"): "cape",
                    }.get((sn, lvl))
                    if not key or key in out:
                        continue
                    a = np.asarray(eccodes.codes_get_values(g), np.float32).reshape(nj, ni)
                    if key == "temp_c":
                        a = a - 273.15
                    elif key == "pressure_hpa":
                        a = a / 100.0
                    elif key == "precip_mm":
                        a = a * 3600.0  # kg m-2 s-1 → mm/h
                    out[key] = a
                finally:
                    eccodes.codes_release(g)
    finally:
        try:
            os.unlink(path)
        except OSError:
            pass
    return out


def _decode_child(blob: bytes, conn) -> None:
    try:
        conn.send(_decode(blob))
    except Exception as exc:
        conn.send(exc)
    finally:
        conn.close()


def _decode_isolated(blob: bytes) -> dict[str, np.ndarray]:
    """Decode in a child process.

    A truncated GRIB makes ecCodes call exit() from its scanner. That would
    kill the API if it ran in this process.
    """
    import multiprocessing as mp

    ctx = mp.get_context("spawn")
    parent, child = ctx.Pipe(duplex=False)
    proc = ctx.Process(target=_decode_child, args=(blob, child))
    proc.start()
    child.close()
    proc.join(180)
    if proc.is_alive():
        proc.kill()
        proc.join(5)
        parent.close()
        raise RuntimeError("grib_decode_timeout")
    try:
        if not parent.poll(2):
            raise RuntimeError(f"grib_decode_exit_{proc.exitcode}")
        result = parent.recv()
    finally:
        parent.close()
    if isinstance(result, BaseException):
        raise result
    return result


def _to_1deg(a: np.ndarray) -> np.ndarray:
    """0.5° GFS (lat 90→−90, lon 0→359.5) → 1°, lat −80…80 ascending, lon −180…179."""
    a = a[::2, ::2]  # 181×360, lat 90..-90, lon 0..359
    a = a[::-1]  # lat -90..90
    a = a[10:171]  # -80..80
    return np.roll(a, 180, axis=1)  # lon -180..179


def _quant(key: str, a: np.ndarray) -> np.ndarray:
    lo, hi, tr = QUANT[key]
    v = np.log1p(np.maximum(a, 0)) if tr == "log1p" else a
    q = np.round((np.clip(v, lo, hi) - lo) / (hi - lo) * 255.0)
    return np.nan_to_num(q, nan=0).astype(np.uint8)


async def _fetch_step(c: datetime, step: int) -> dict[str, np.ndarray]:
    from app.providers.http import client

    params = {
        "dir": f"/gfs.{c:%Y%m%d}/{c:%H}/atmos",
        "file": f"gfs.t{c:%H}z.pgrb2full.0p50.f{step:03d}",
        "var_TMP": "on", "var_RH": "on", "var_UGRD": "on", "var_VGRD": "on", "var_PRMSL": "on",
        "var_TCDC": "on", "var_PRATE": "on", "var_CAPE": "on",
        "lev_2_m_above_ground": "on", "lev_10_m_above_ground": "on", "lev_mean_sea_level": "on",
        "lev_entire_atmosphere": "on", "lev_surface": "on",
    }
    r = await client().get(FILTER, params=params, timeout=120.0)
    if r.status_code >= 400 or not r.content.startswith(b"GRIB"):
        raise RuntimeError(f"nomads http_{r.status_code}")
    raw = await asyncio.to_thread(_decode_isolated, r.content)
    return {k: _quant(k, _to_1deg(v)) for k, v in raw.items()}


async def _load_cycle(c: datetime) -> dict[int, dict[str, np.ndarray]]:
    path = _dir() / f"gfs_{c:%Y%m%d%H}.npz"
    if path.exists():
        z = np.load(path)
        out: dict[int, dict[str, np.ndarray]] = {}
        for name in z.files:
            s, k = name.split("__", 1)
            out.setdefault(int(s), {})[k] = z[name]
        if len(out) == len(STEPS):
            return out
    out = {}
    sem = asyncio.Semaphore(2)  # be polite to NOMADS and the user's link

    async def one(s: int):
        async with sem:
            out[s] = await _fetch_step(c, s)

    await asyncio.gather(*(one(s) for s in STEPS))
    np.savez_compressed(path, **{f"{s}__{k}": v for s, d in out.items() for k, v in d.items()})
    for old in _dir().glob("gfs_*.npz"):
        if old != path:
            try:
                old.unlink()
            except OSError:
                pass
    return out


def _om_to_fields(pack: dict[str, Any]) -> dict[str, np.ndarray]:
    """Resample an Open-Meteo world-grid pack onto the 1° GFS PNG raster."""
    lats = np.asarray(pack.get("lats") or [], dtype=np.float64)
    lons = np.asarray(pack.get("lons") or [], dtype=np.float64)
    raw_fields = pack.get("fields") or {}
    tlat = np.linspace(LAT_S, LAT_N, NY)
    tlon = np.linspace(-180.0, 179.0, NX)
    out: dict[str, np.ndarray] = {}
    if lats.size < 2 or lons.size < 2:
        z = np.zeros((NY, NX), dtype=np.uint8)
        return {k: z.copy() for k in QUANT}
    order = np.argsort(lats)
    lats = lats[order]
    yi = np.interp(tlat, lats, np.arange(len(lats)))
    xi = np.interp(tlon, lons, np.arange(len(lons)))
    I, J = np.meshgrid(yi, xi, indexing="ij")
    i0 = np.clip(np.floor(I).astype(int), 0, len(lats) - 2)
    j0 = np.clip(np.floor(J).astype(int), 0, len(lons) - 2)
    di = I - i0
    dj = J - j0
    for key in QUANT:
        vals = raw_fields.get(key)
        if not vals:
            out[key] = np.zeros((NY, NX), dtype=np.uint8)
            continue
        grid = np.asarray(vals, dtype=np.float64).reshape(len(order), len(lons))[order]
        grid = np.nan_to_num(grid, nan=0.0)
        sampled = (
            grid[i0, j0] * (1 - di) * (1 - dj)
            + grid[i0, j0 + 1] * (1 - di) * dj
            + grid[i0 + 1, j0] * di * (1 - dj)
            + grid[i0 + 1, j0 + 1] * di * dj
        )
        out[key] = _quant(key, sampled)
    return out


async def _fill_from_open_meteo(hour_ahead: int = 0) -> dict[str, Any]:
    """Serve GFS-shaped map layers from the existing Open-Meteo world grid (no GRIB)."""
    from app.providers.weather_grid import world_grid

    hour = max(0, min(23, int(hour_ahead)))
    pack = await world_grid(hour)
    fields = _om_to_fields(pack)
    now = datetime.now(UTC).replace(minute=0, second=0, microsecond=0)
    valid = pack.get("valid")
    if valid:
        try:
            stamp = datetime.fromisoformat(str(valid).replace("Z", "+00:00"))
            if stamp.tzinfo is None:
                stamp = stamp.replace(tzinfo=UTC)
            now = stamp.astimezone(UTC).replace(minute=0, second=0, microsecond=0)
        except ValueError:
            pass
    step = min(STEPS, key=lambda s: abs(s - hour))
    ok = bool(pack.get("ok", True))
    _STATE.update(
        cycle=now - timedelta(hours=step),
        fields={step: fields},
        status="ok" if ok else "error",
        checked=time.time(),
        error=None if ok else str(pack.get("note") or "open-meteo unavailable")[:160],
        source="Open-Meteo GFS/IFS (no local GRIB decode)",
        load_s=None,
    )
    return status()


async def ensure(hour_ahead: int = 0) -> dict[str, Any]:
    """Make sure map layers are ready. GRIB on a local PC; Open-Meteo on cloud."""
    if decode_enabled():
        kick()
        return status()
    async with _LOCK:
        fresh = (
            _STATE["fields"] is not None
            and _STATE.get("source")
            and "open-meteo" in str(_STATE.get("source")).lower()
            and time.time() - _STATE["checked"] < 45 * 60
            and pick_step(hour_ahead) is not None
        )
        if fresh:
            return status()
        return await _fill_from_open_meteo(hour_ahead)


async def refresh(force: bool = False) -> dict[str, Any]:
    if not decode_enabled():
        return await ensure()
    async with _LOCK:
        if not force and _STATE["fields"] is not None and time.time() - _STATE["checked"] < 45 * 60:
            return status()
        try:
            import eccodes  # noqa: F401
        except ImportError:
            _STATE.update(status="eccodes_missing", checked=time.time())
            return status()
        _STATE["status"] = "checking"
        try:
            c = await latest_cycle()
            _STATE["checked"] = time.time()
            if c is None:
                _STATE["status"] = "no_cycle"
            elif c != _STATE["cycle"] or _STATE["fields"] is None:
                _STATE["status"] = "downloading"
                t0 = time.time()
                fields = await _load_cycle(c)
                _STATE.update(cycle=c, fields=fields, status="ok", load_s=round(time.time() - t0, 1), error=None)
            else:
                _STATE["status"] = "ok"
        except Exception as e:  # noqa: BLE001
            _STATE.update(status="error", error=str(e)[:160], checked=time.time())
        return status()


def kick() -> None:
    """Start a background GRIB refresh. No-op on cloud (use ensure() / Open-Meteo instead)."""
    global _TASK
    if not decode_enabled():
        return
    fresh = _STATE["fields"] is not None and time.time() - _STATE["checked"] < 45 * 60
    if fresh or (_TASK is not None and not _TASK.done()):
        return
    try:
        _TASK = asyncio.get_running_loop().create_task(refresh())
    except RuntimeError:
        pass


def status() -> dict[str, Any]:
    c = _STATE["cycle"]
    src = _STATE.get("source")
    if not src:
        src = (
            "NOAA GFS 0.5° (NOMADS), served at 1°"
            if decode_enabled()
            else "Open-Meteo GFS/IFS (no local GRIB decode)"
        )
    return {
        "ok": _STATE["fields"] is not None,
        "status": _STATE["status"],
        "error": _STATE.get("error"),
        "cycle": c.isoformat() if c else None,
        "load_s": _STATE.get("load_s"),
        "source": src,
        "decode": decode_enabled(),
    }


def pick_step(hour_ahead: int) -> tuple[int, datetime] | None:
    c = _STATE["cycle"]
    if c is None or _STATE["fields"] is None:
        return None
    target = datetime.now(UTC) + timedelta(hours=hour_ahead)
    lead = (target - c).total_seconds() / 3600.0
    step = min(STEPS, key=lambda s: abs(s - lead))
    return step, c + timedelta(hours=step)


def meta(hour_ahead: int) -> dict[str, Any]:
    if decode_enabled():
        kick()
    st = status()
    ps = pick_step(hour_ahead)
    if not ps:
        return {**st, "ok": False}
    step, valid = ps
    return {
        **st,
        "step": step,
        "valid": valid.isoformat(),
        "grid": {"nx": NX, "ny": NY, "south": LAT_S, "north": LAT_N, "west": -180.0, "dlon": 1.0, "dlat": 1.0},
        "quant": {k: {"min": lo, "max": hi, "transform": tr} for k, (lo, hi, tr) in QUANT.items()},
        "fields": sorted(_STATE["fields"][step].keys()),
        "source": st.get("source") or "NOAA GFS 0.5° (NOMADS), served at 1°",
    }


def png(field: str, step: int) -> bytes | None:
    from PIL import Image

    d = (_STATE["fields"] or {}).get(step) or {}
    a = d.get(field)
    if a is None:
        return None
    buf = io.BytesIO()
    # Row 0 = north (image convention).
    Image.fromarray(np.ascontiguousarray(a[::-1])).save(buf, format="PNG", optimize=True)
    return buf.getvalue()

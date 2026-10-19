"""NASA GIBS WMS: live IR and IMERG tiles. No key."""

from __future__ import annotations

import io
from datetime import datetime, timezone
from typing import Any

from app import cache
from app.providers.http import client

WMS = "https://gibs.earthdata.nasa.gov/wms/epsg4326/best/wms.cgi"
# Only layers that exist in GIBS "best" (checked against WMTS GetCapabilities, Oct 2026).
# GPM_3IMERGHH_06_precipitationCal / GPM_3IMERGHHE_06_precipitationCal and the MODIS/VIIRS
# brightness-temperature names returned WMS XML errors, so they were removed.
IR_LAYERS = ("Himawari_AHI_Band13_Clean_Infrared",)
IMERG_LAYERS = ("IMERG_Precipitation_Rate",)
# One shared India frame per layer/time instead of one WMS call per pin.
FRAME_BBOX = (5.0, 65.0, 38.0, 100.0)  # south, west, north, east (EPSG:4326 axis order lat,lon)
FRAME_W, FRAME_H = 560, 528  # 0.0625° pixels

_LUTS: dict[str, dict[tuple[int, int, int], float | None]] = {}


def _lut(key: str) -> dict[tuple[int, int, int], float | None]:
    """RGB → value from NASA GIBS colormap XML (v1.3), shipped as app/data/gibs_colormaps.json."""
    if key in _LUTS:
        return _LUTS[key]
    import json
    from pathlib import Path

    blob = json.loads((Path(__file__).resolve().parents[1] / "data" / "gibs_colormaps.json").read_text())
    _LUTS[key] = {(r, g, b): v for r, g, b, v in blob[key]["entries"]}
    return _LUTS[key]


def _decode_value(rgba: tuple[int, int, int, int], key: str) -> tuple[bool, float | None]:
    """(has_data, value). Transparent pixels are 'no value' (nodata or below the first bin)."""
    r, g, b, a = rgba
    if a == 0:
        return False, None
    lut = _lut(key)
    v = lut.get((r, g, b), "miss")
    if v == "miss":
        best, bd = None, 1e9
        for (rr, gg, bb), vv in lut.items():
            d = (rr - r) ** 2 + (gg - g) ** 2 + (bb - b) ** 2
            if d < bd:
                best, bd = vv, d
        v = best if bd <= 300 else None
    return v is not None, v


def ir_candidate_times(now: datetime | None = None) -> list[str]:
    """Himawari is 10-minute; GIBS lags ~20–40 min. A date-only TIME returns 00:00Z (stale)."""
    from datetime import timedelta

    now = now or datetime.now(timezone.utc)
    base = now - timedelta(minutes=20)
    base = base.replace(minute=base.minute - base.minute % 10, second=0, microsecond=0)
    return [(base - timedelta(minutes=10 * k)).strftime("%Y-%m-%dT%H:%M:%SZ") for k in range(4)]


def imerg_candidate_times(now: datetime | None = None) -> list[str]:
    """GIBS IMERG_Precipitation_Rate is effectively one image per day; today is often empty."""
    from datetime import timedelta

    now = now or datetime.now(timezone.utc)
    return [(now - timedelta(days=k)).strftime("%Y-%m-%d") for k in range(3)]


async def _get_frame(layer: str, time_str: str) -> bytes | None:
    s, w, n, e = FRAME_BBOX
    params = {
        "SERVICE": "WMS",
        "REQUEST": "GetMap",
        "VERSION": "1.3.0",
        "LAYERS": layer,
        "CRS": "EPSG:4326",
        "BBOX": f"{s},{w},{n},{e}",
        "WIDTH": str(FRAME_W),
        "HEIGHT": str(FRAME_H),
        "FORMAT": "image/png",
        "TRANSPARENT": "TRUE",
        "TIME": time_str,
    }
    r = await client().get(WMS, params=params, timeout=8.0)
    if r.status_code >= 400:
        return None
    ctype = (r.headers.get("content-type") or "").lower()
    if "image" not in ctype or len(r.content) < 80:
        return None
    return r.content


def _rgba(png: bytes):
    import numpy as np
    from PIL import Image

    return np.asarray(Image.open(io.BytesIO(png)).convert("RGBA"))


async def frame(kind: str) -> dict[str, Any]:
    """Latest non-empty India frame for kind 'ir' or 'imerg' (cached, single-flight)."""
    import asyncio

    ck = f"gibs:frame:{kind}"
    hit = cache.get(ck)
    if isinstance(hit, dict):
        return hit
    lock = _LOCKS.setdefault(kind, asyncio.Lock())
    async with lock:
        hit = cache.get(ck)
        if isinstance(hit, dict):
            return hit
        layer = IR_LAYERS[0] if kind == "ir" else IMERG_LAYERS[0]
        times = ir_candidate_times() if kind == "ir" else imerg_candidate_times()
        status = "empty"

        async def get(t: str) -> tuple[str, Any]:
            try:
                raw = await _get_frame(layer, t)
            except Exception as e:
                return t, f"error:{type(e).__name__}"
            if not raw:
                return t, "http_error"
            arr = await asyncio.to_thread(_rgba, raw)
            if int((arr[..., 3] > 0).sum()) == 0:
                return t, "no_data"  # fully transparent → not available yet (NOT "dry")
            return t, arr

        # All candidate times in parallel; keep the newest one that has data.
        results = await asyncio.gather(*(get(t) for t in times[:3]))
        for t, res in results:
            if isinstance(res, str):
                status = res
                continue
            out = {"ok": True, "layer": layer, "valid": t, "rgba": res, "status": "ok"}
            cache.set(ck, out, 600 if kind == "ir" else 1800)
            return out
        fail = {"ok": False, "layer": layer, "valid": None, "rgba": None, "status": status}
        cache.set(ck, fail, 120)
        return fail


_LOCKS: dict[str, Any] = {}


def _pix(lat: float, lon: float) -> tuple[int, int] | None:
    s, w, n, e = FRAME_BBOX
    if not (s <= lat <= n and w <= lon <= e):
        return None
    x = int((lon - w) / (e - w) * (FRAME_W - 1) + 0.5)
    y = int((n - lat) / (n - s) * (FRAME_H - 1) + 0.5)
    return x, y


def _patch(arr, lat: float, lon: float, half_deg: float, key: str, n: int, to_k: bool) -> list[list[float | None]]:
    out: list[list[float | None]] = []
    for j in range(n):
        plat = lat + half_deg - (j + 0.5) * (2 * half_deg / n)
        row: list[float | None] = []
        for i in range(n):
            plon = lon - half_deg + (i + 0.5) * (2 * half_deg / n)
            p = _pix(plat, plon)
            if p is None:
                row.append(None)
                continue
            ok, v = _decode_value(tuple(int(c) for c in arr[p[1], p[0]]), key)
            if to_k:
                row.append(round(v + 273.15, 1) if ok and v is not None else None)
            else:
                row.append(round(v, 2) if ok and v is not None else 0.0)
        out.append(row)
    return out


async def fetch_ir(lat: float, lon: float) -> dict[str, Any]:
    """Himawari-9 AHI B13 Tb (K) decoded with the GIBS colormap at the latest real frame."""
    fr = await frame("ir")
    if not fr.get("ok"):
        return {"ok": False, "source": "gibs-ir", "status": fr.get("status"), "tb_k": None, "cold_frac": 0.0, "grid": None}
    arr = fr["rgba"]
    grid = _patch(arr, lat, lon, 1.1, "ir_c", 36, to_k=True)
    p = _pix(lat, lon)
    tb = None
    if p:
        ok, v = _decode_value(tuple(int(c) for c in arr[p[1], p[0]]), "ir_c")
        tb = round(v + 273.15, 1) if ok and v is not None else None
    vals = [v for row in grid for v in row if v is not None]
    # sat_cv expects a dense grid; masked pixels → warm background
    dense = [[v if v is not None else 300.0 for v in row] for row in grid]
    return {
        "ok": tb is not None or bool(vals),
        "source": "gibs-ir",
        "layer": fr["layer"],
        "valid": fr["valid"],
        "tb_k": tb,
        "tb_kind": "colormap-decoded",
        "cold_frac": round(sum(1 for v in vals if v <= 235.0) / max(1, len(vals)), 3),
        "grid": dense,
        "status": "ok",
    }


async def fetch_imerg(lat: float, lon: float) -> dict[str, Any]:
    """IMERG rate (mm/h) at the pin from the latest *non-empty* GIBS day; None if unavailable."""
    fr = await frame("imerg")
    if not fr.get("ok"):
        return {
            "ok": False,
            "source": "gibs-imerg",
            "status": fr.get("status"),
            "mm_h": None,
            "valid": None,
            "source_kind": "satellite-qpe",
            "note": "IMERG not yet available in GIBS — shown as missing, not as 0 mm/h.",
        }
    arr = fr["rgba"]
    p = _pix(lat, lon)
    mm = None
    if p:
        ok, v = _decode_value(tuple(int(c) for c in arr[p[1], p[0]]), "imerg_mm_h")
        mm = round(v, 2) if ok and v is not None else 0.0  # frame has data → transparent = < 0.1 mm/h
    return {
        "ok": mm is not None,
        "source": "gibs-imerg",
        "layer": fr["layer"],
        "valid": fr["valid"],
        "mm_h": mm,
        "source_kind": "satellite-qpe",
        "status": "ok",
        "note": f"GIBS IMERG image for {fr['valid']} (not real-time).",
    }

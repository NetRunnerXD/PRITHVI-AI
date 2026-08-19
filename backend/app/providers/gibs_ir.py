"""NASA GIBS WMS: live IR and IMERG tiles. No key."""

from __future__ import annotations

import io
from datetime import datetime, timezone
from typing import Any

from app import cache
from app.providers.http import client

WMS = "https://gibs.earthdata.nasa.gov/wms/epsg4326/best/wms.cgi"
IR_LAYERS = (
    "Himawari_AHI_Band13_Clean_Infrared",
    "MODIS_Aqua_Brightness_Temp_Band31_Night",
    "MODIS_Terra_Brightness_Temp_Band31_Night",
    "MODIS_Aqua_Brightness_Temp_Band31_Day",
    "VIIRS_SNPP_Brightness_Temp_BandI5_Night",
)
IMERG_LAYERS = (
    "GPM_3IMERGHH_06_precipitationCal",
    "IMERG_Precipitation_Rate",
    "GPM_3IMERGHHE_06_precipitationCal",
)


def _bbox(lat: float, lon: float, half: float = 1.0) -> str:
    south = max(-89.0, lat - half)
    north = min(89.0, lat + half)
    west = lon - half
    east = lon + half
    return f"{south:.3f},{west:.3f},{north:.3f},{east:.3f}"


def decode_gray(png: bytes) -> list[list[int]] | None:
    try:
        from PIL import Image
    except ImportError:
        return None
    try:
        im = Image.open(io.BytesIO(png)).convert("L")
    except Exception:
        return None
    w, h = im.size
    pix = list(im.getdata())
    return [pix[i * w : (i + 1) * w] for i in range(h)]


def decode_rgb(png: bytes) -> list[list[tuple[int, int, int]]] | None:
    try:
        from PIL import Image
    except ImportError:
        return None
    try:
        im = Image.open(io.BytesIO(png)).convert("RGB")
    except Exception:
        return None
    w, h = im.size
    pix = list(im.getdata())
    return [pix[i * w : (i + 1) * w] for i in range(h)]


def gray_to_tb(grid: list[list[int]]) -> list[list[float]]:
    """GIBS IR colour ramps vary; luminance as Tb proxy (bright ≈ cold)."""
    out: list[list[float]] = []
    for row in grid:
        out.append([round(310.0 - 90.0 * (p / 255.0), 1) for p in row])
    return out


def rgb_to_mmh(grid: list[list[tuple[int, int, int]]]) -> list[list[float]]:
    """IMERG-style ramp: dark=0, green/yellow/red = heavier rain."""
    out: list[list[float]] = []
    for row in grid:
        line: list[float] = []
        for r, g, b in row:
            if r < 12 and g < 12 and b < 12:
                line.append(0.0)
                continue
            line.append(round(min(80.0, (r * 0.12 + g * 0.04 + max(0, 180 - b) * 0.05)), 2))
        out.append(line)
    return out


async def _get_map(layer: str, lat: float, lon: float, size: int = 80) -> bytes | None:
    params = {
        "SERVICE": "WMS",
        "REQUEST": "GetMap",
        "VERSION": "1.3.0",
        "LAYERS": layer,
        "CRS": "EPSG:4326",
        "BBOX": _bbox(lat, lon, 1.1),
        "WIDTH": str(size),
        "HEIGHT": str(size),
        "FORMAT": "image/png",
        "TIME": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
    }
    r = await client().get(WMS, params=params)
    if r.status_code >= 400:
        return None
    ctype = (r.headers.get("content-type") or "").lower()
    if "png" not in ctype and "image" not in ctype:
        return None
    if len(r.content) < 80:
        return None
    return r.content


async def fetch_ir(lat: float, lon: float) -> dict[str, Any]:
    ck = f"gibs:ir:{round(lat, 2)}:{round(lon, 2)}"
    hit = cache.get(ck)
    if isinstance(hit, dict):
        return hit
    last_err = "empty"
    for layer in IR_LAYERS:
        try:
            raw = await _get_map(layer, lat, lon)
        except Exception:
            last_err = "error"
            continue
        if not raw:
            continue
        gray = decode_gray(raw)
        if not gray:
            last_err = "decode"
            continue
        tb = gray_to_tb(gray)
        mid = tb[len(tb) // 2][len(tb[0]) // 2]
        cold = sum(1 for row in tb for v in row if v <= 235.0)
        n = max(1, sum(len(row) for row in tb))
        out = {
            "ok": True,
            "source": "gibs-ir",
            "layer": layer,
            "tb_k": mid,
            "cold_frac": round(cold / n, 3),
            "grid": tb,
            "status": "ok",
        }
        slim = {k: v for k, v in out.items() if k != "grid"}
        cache.set(ck, slim, 180)
        return out
    fail = {"ok": False, "source": "gibs-ir", "status": last_err, "tb_k": None, "cold_frac": 0.0, "grid": None}
    cache.set(ck, fail, 90)
    return fail


async def fetch_imerg(lat: float, lon: float) -> dict[str, Any]:
    ck = f"gibs:imerg:{round(lat, 2)}:{round(lon, 2)}"
    hit = cache.get(ck)
    if isinstance(hit, dict):
        return hit
    last_err = "empty"
    for layer in IMERG_LAYERS:
        try:
            raw = await _get_map(layer, lat, lon, size=64)
        except Exception:
            last_err = "error"
            continue
        if not raw:
            continue
        rgb = decode_rgb(raw)
        if not rgb:
            last_err = "decode"
            continue
        mm = rgb_to_mmh(rgb)
        mid = mm[len(mm) // 2][len(mm[0]) // 2]
        out = {
            "ok": True,
            "source": "gibs-imerg",
            "layer": layer,
            "mm_h": mid,
            "source_kind": "satellite-qpe",
            "status": "ok",
        }
        cache.set(ck, out, 180)
        return out
    fail = {"ok": False, "source": "gibs-imerg", "status": last_err, "mm_h": None, "source_kind": "satellite-qpe"}
    cache.set(ck, fail, 90)
    return fail

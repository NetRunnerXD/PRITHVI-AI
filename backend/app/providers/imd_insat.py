"""Public IMD INSAT-3D/3DS Asia-sector IR JPEG. No MOSDAC login.

HEM/IMR HDF is not on this path. The IR1 image is the live Indian geostationary
frame IMD publishes for humans — we georeference the Asia sector and sample
the pin. That is INSAT imagery, not a rain-gauge and not HEM millimetres.
"""

from __future__ import annotations

import io
from typing import Any

from app import cache
from app.providers.http import client

# Tried in order. First PNG/JPEG win is used.
IR_URLS = (
    "https://mausam.imd.gov.in/Satellite/3Dasiasec_ir1.jpg",
    "https://satellite.imd.gov.in/img/3Dasiasec_ir1.jpg",
    "https://mausam.imd.gov.in/Satellite/3RIMG_IR1.jpg",
    "https://mausam.imd.gov.in/imd_latest/contents/satellite.php",
)

# Approximate geolocation of IMD 3D Asia-sector IR (full-disk crop used on the site).
# lon west, lon east, lat south, lat north
ASIA_BOUNDS = (40.0, 130.0, -40.0, 40.0)
# Tight India crop. Tibet / Yunnan still sit inside a rectangle — pixels
# outside the political outline are warmed to 300 K in downsample_india.
INDIA_BOUNDS = (68.1, 97.4, 6.6, 35.8)


def _sample_gray(png: bytes, lat: float, lon: float) -> dict[str, Any] | None:
    try:
        from PIL import Image
    except ImportError:
        return None
    try:
        im = Image.open(io.BytesIO(png)).convert("L")
    except Exception:
        return None
    w, h = im.size
    if w < 20 or h < 20:
        return None
    west, east, south, north = ASIA_BOUNDS
    if not (west <= lon <= east and south <= lat <= north):
        return {"ok": False, "status": "off_frame", "tb_k": None, "gray": None}
    x = int(round((lon - west) / (east - west) * (w - 1)))
    y = int(round((north - lat) / (north - south) * (h - 1)))
    x = max(1, min(w - 2, x))
    y = max(1, min(h - 2, y))
    pix = im.load()
    vals = [pix[x + dx, y + dy] for dy in (-1, 0, 1) for dx in (-1, 0, 1)]
    g = sum(vals) / len(vals)
    # IMD IR display: bright / white = cold high cloud.
    tb = round(310.0 - 95.0 * (g / 255.0), 1)
    half = 6
    x0, x1 = max(0, x - half), min(w, x + half)
    y0, y1 = max(0, y - half), min(h, y + half)
    patch: list[list[float]] = []
    for yy in range(y0, y1):
        row = []
        for xx in range(x0, x1):
            row.append(round(310.0 - 95.0 * (pix[xx, yy] / 255.0), 1))
        patch.append(row)
    return {"ok": True, "status": "ok", "tb_k": tb, "gray": round(g, 1), "grid": patch, "px": [x, y], "size": [w, h]}


def downsample_india(png: bytes, size: int = 140) -> list[list[float]] | None:
    """Crop the Asia-sector JPEG to India and resample for cell finding."""
    try:
        from PIL import Image
    except ImportError:
        return None
    try:
        im = Image.open(io.BytesIO(png)).convert("L")
    except Exception:
        return None
    w, h = im.size
    if w < 40 or h < 40:
        return None
    west, east, south, north = ASIA_BOUNDS
    iw, ie, iso, ino = INDIA_BOUNDS
    x0 = int((iw - west) / (east - west) * (w - 1))
    x1 = int((ie - west) / (east - west) * (w - 1))
    y0 = int((north - ino) / (north - south) * (h - 1))
    y1 = int((north - iso) / (north - south) * (h - 1))
    x0, x1 = max(0, min(x0, x1)), min(w, max(x0, x1))
    y0, y1 = max(0, min(y0, y1)), min(h, max(y0, y1))
    if x1 - x0 < 8 or y1 - y0 < 8:
        return None
    crop = im.crop((x0, y0, x1, y1)).resize((size, size))
    pix = list(crop.getdata())
    from app.data.india_mask import in_india

    grid: list[list[float]] = []
    for y in range(size):
        lat = ino - (y + 0.5) / size * (ino - iso)
        row = []
        for x in range(size):
            lon = iw + (x + 0.5) / size * (ie - iw)
            if not in_india(lat, lon):
                row.append(300.0)
                continue
            g = pix[y * size + x]
            row.append(round(310.0 - 95.0 * (g / 255.0), 1))
        grid.append(row)
    return grid


def downsample_sector(png: bytes, size: int = 80) -> list[list[float]] | None:
    try:
        from PIL import Image
    except ImportError:
        return None
    try:
        im = Image.open(io.BytesIO(png)).convert("L").resize((size, size))
    except Exception:
        return None
    pix = list(im.getdata())
    grid: list[list[float]] = []
    for y in range(size):
        row = []
        for x in range(size):
            g = pix[y * size + x]
            row.append(round(310.0 - 95.0 * (g / 255.0), 1))
        grid.append(row)
    return grid


async def fetch_ir(lat: float, lon: float) -> dict[str, Any]:
    ck = f"imd:insat:{round(lat, 2)}:{round(lon, 2)}"
    hit = cache.get(ck)
    if isinstance(hit, dict):
        return hit
    last = "empty"
    for url in IR_URLS:
        if url.endswith(".php"):
            continue
        try:
            r = await client().get(url)
        except Exception:
            last = "error"
            continue
        if r.status_code >= 400:
            last = f"http_{r.status_code}"
            continue
        ctype = (r.headers.get("content-type") or "").lower()
        body = r.content
        if len(body) < 400:
            last = "tiny"
            continue
        if "html" in ctype:
            last = "html"
            continue
        sampled = _sample_gray(body, lat, lon)
        if not sampled:
            last = "decode"
            continue
        out = {
            **sampled,
            "source": "imd-insat-ir1",
            "source_kind": "satellite-ir",
            "url": url,
            "product": "INSAT-3D/3DS Asia-sector IR1 (public JPEG)",
        }
        slim = {k: v for k, v in out.items() if k != "grid"}
        cache.set(ck, slim, 180)
        return out
    fail = {
        "ok": False,
        "source": "imd-insat-ir1",
        "source_kind": "satellite-ir",
        "status": last,
        "tb_k": None,
        "grid": None,
    }
    cache.set(ck, fail, 90)
    return fail


async def fetch_sector() -> dict[str, Any]:
    """Downsampled full Asia-sector IR for All-India cell finding."""
    ck = "imd:insat:sector"
    hit = cache.get(ck)
    if isinstance(hit, dict) and hit.get("grid"):
        return hit
    last = "empty"
    for url in IR_URLS:
        if url.endswith(".php"):
            continue
        try:
            r = await client().get(url)
        except Exception:
            last = "error"
            continue
        if r.status_code >= 400 or len(r.content) < 400:
            last = "http"
            continue
        if "html" in (r.headers.get("content-type") or "").lower():
            last = "html"
            continue
        grid = downsample_india(r.content, 140) or downsample_sector(r.content, 80)
        if not grid:
            last = "decode"
            continue
        bounds = INDIA_BOUNDS if grid and len(grid) >= 100 else ASIA_BOUNDS
        out = {
            "ok": True,
            "source": "imd-insat-ir1",
            "source_kind": "satellite-ir",
            "bounds": bounds,
            "grid": grid,
            "status": "ok",
        }
        cache.set(ck, out, 180)
        return out
    fail = {"ok": False, "source": "imd-insat-ir1", "status": last, "grid": None, "bounds": ASIA_BOUNDS}
    cache.set(ck, fail, 90)
    return fail

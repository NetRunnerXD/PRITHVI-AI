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

# Tried in order. First JPEG win is used. (satellite.imd.gov.in now answers 401 and
# 3RIMG_IR1.jpg 404 — both removed so a miss does not cost two extra round-trips.)
IR_URLS = ("https://mausam.imd.gov.in/Satellite/3Dasiasec_ir1.jpg",)

# INSAT-3D/3DS Asia-sector public JPEGs: VIS / TIR / WV.
# SWIR (3Dasiasec_swir.jpg) and MIR (3Dasiasec_mir.jpg) return 404 (checked Oct 2026): removed.
CHANNELS = (
    ("VIS 0.65μm", ("https://mausam.imd.gov.in/Satellite/3Dasiasec_vis.jpg",)),
    ("TIR 10.8μm", IR_URLS),
    ("WV 6.7μm", ("https://mausam.imd.gov.in/Satellite/3Dasiasec_wv.jpg",)),
)

# Nominal IMD SATMET Asiamer sector: 10°S–45°N, 40°E–110°E (lon west, lon east, lat south, lat north).
ASIA_BOUNDS = (40.0, 110.0, -10.0, 45.0)
# Tight India crop. Pixels outside the political outline are warmed to 300 K.
INDIA_BOUNDS = (68.1, 97.4, 6.6, 35.8)
# Legacy fixed-fraction chrome crop. NOT used for georeferencing any more: the
# 3DS "L1C MERCATOR" JPEG has no right colour bar and a ~11 % header, so this
# crop shifted every pixel ~5° N and 2–5° W (500–770 km). Kept for callers/tests.
CHROME_LTRB = (0.042, 0.078, 0.118, 0.052)

# Georeference of the 3Dasiasec_ir1.jpg layout (2002×2242 px, "L1C MERCATOR"), fitted
# on the drawn graticule (19 Oct 2026): x = A·lon + B ; y = Y0 + K·ln tan(π/4 + φ/2).
# Residuals < 0.5 px at 50/60/70/90/100°E and 0/10/20/30/40°N.
REF_SIZE = (2002, 2242)
REF_A, REF_B = 28.571, -1142.8
REF_K, REF_Y0 = -1870.3, 1912.2
REF_MAP_TOP = 245  # first image row below the title/colour-bar header
GRAY_TB_NOTE = (
    "Uncalibrated IR brightness proxy: the public JPEG is a per-scene 1 % linear stretch of "
    "TIR1 counts, so grey→K is approximate (310−95·g/255). Use MOSDAC L1C Tb for physics."
)


def _merc(lat_deg: float) -> float:
    import math

    lat = max(-85.0, min(85.0, float(lat_deg)))
    return math.log(math.tan(math.pi / 4 + math.radians(lat) / 2))


def _inv_merc(m: float) -> float:
    import math

    return math.degrees(math.atan(math.sinh(m)))


class Georef:
    """Pixel <-> lat/lon for the IMD Mercator Asia-sector JPEG (full, uncropped image)."""

    def __init__(self, a: float, b: float, k: float, y0: float, map_top: int, size: tuple[int, int]):
        self.a, self.b, self.k, self.y0, self.map_top, self.size = a, b, k, y0, map_top, size

    @classmethod
    def for_size(cls, w: int, h: int) -> "Georef":
        sx, sy = w / REF_SIZE[0], h / REF_SIZE[1]
        return cls(REF_A * sx, REF_B * sx, REF_K * sy, REF_Y0 * sy, int(round(REF_MAP_TOP * sy)), (w, h))

    def px(self, lat: float, lon: float) -> tuple[float, float]:
        return self.a * lon + self.b, self.y0 + self.k * _merc(lat)

    def latlon(self, x: float, y: float) -> tuple[float, float]:
        return _inv_merc((y - self.y0) / self.k), (x - self.b) / self.a

    def bounds(self) -> tuple[float, float, float, float]:
        """(west, east, south, north) of the map area (below the header)."""
        w, h = self.size
        north, west = self.latlon(0, self.map_top)
        south, east = self.latlon(w - 1, h - 1)
        return (round(west, 3), round(east, 3), round(south, 3), round(north, 3))


def _overlay_mask(rgb):
    """True where IMD drew borders/coasts (coloured) or the dashed graticule (grey lines)."""
    import numpy as np

    a = rgb.astype(np.int16)
    chroma = a.max(axis=2) - a.min(axis=2)
    mask = chroma > 40
    gray = a.mean(axis=2)
    # graticule: thin rows/columns that stand out from both neighbours along most of the image
    d_row = np.abs(gray[1:-1] - 0.5 * (gray[:-2] + gray[2:])) > 25
    d_col = np.abs(gray[:, 1:-1] - 0.5 * (gray[:, :-2] + gray[:, 2:])) > 25
    rows = np.nonzero(d_row.mean(axis=1) > 0.18)[0] + 1
    cols = np.nonzero(d_col.mean(axis=0) > 0.18)[0] + 1
    for r in rows:
        mask[max(0, r - 1) : r + 2, :] = True
    for c in cols:
        mask[:, max(0, c - 1) : c + 2] = True
    # grow 1 px so JPEG ringing around lines is dropped too
    grown = mask.copy()
    grown[1:] |= mask[:-1]
    grown[:-1] |= mask[1:]
    grown[:, 1:] |= mask[:, :-1]
    grown[:, :-1] |= mask[:, 1:]
    return grown


def _decode(png: bytes):
    try:
        import numpy as np
        from PIL import Image
    except ImportError:
        return None
    try:
        im = Image.open(io.BytesIO(png)).convert("RGB")
    except Exception:
        return None
    rgb = np.asarray(im)
    if rgb.shape[0] < 80 or rgb.shape[1] < 80:
        return None
    return rgb


def _gray_tb(g: float) -> float:
    return round(310.0 - 95.0 * (g / 255.0), 1)


def crop_chrome(png: bytes) -> bytes:
    """Legacy fixed-fraction crop (kept for tests). Do not georeference its output."""
    try:
        from PIL import Image
    except ImportError:
        return png
    try:
        im = Image.open(io.BytesIO(png)).convert("RGB")
    except Exception:
        return png
    w, h = im.size
    if w < 80 or h < 80:
        return png
    l, t, r, b = CHROME_LTRB
    box = (int(w * l), int(h * t), int(w * (1 - r)), int(h * (1 - b)))
    if box[2] - box[0] < 40 or box[3] - box[1] < 40:
        return png
    out = io.BytesIO()
    im.crop(box).save(out, format="JPEG", quality=85)
    return out.getvalue()


def map_area_jpeg(png: bytes) -> tuple[bytes, tuple[float, float, float, float]] | None:
    """Header removed → a pure Web-Mercator image whose corners are bounds() (for Leaflet)."""
    try:
        from PIL import Image
    except ImportError:
        return None
    try:
        im = Image.open(io.BytesIO(png)).convert("RGB")
    except Exception:
        return None
    w, h = im.size
    geo = Georef.for_size(w, h)
    crop = im.crop((0, geo.map_top, w, h))
    if crop.width > 1200:  # ~4× fewer bytes; plenty for a zoom-5 overlay
        crop = crop.resize((1200, int(crop.height * 1200 / crop.width)), Image.BILINEAR)
    out = io.BytesIO()
    crop.save(out, format="JPEG", quality=80, optimize=True, progressive=True)
    return out.getvalue(), geo.bounds()


ASIA_MAP_BOUNDS = Georef.for_size(*REF_SIZE).bounds()  # (west, east, south, north) of the Mercator map area


async def map_area() -> dict[str, Any]:
    """Cropped map-area JPEG + Leaflet bounds, cached per image valid time."""
    import asyncio

    fr = await fetch_frame()
    body = fr.get("body")
    if not body:
        return {"ok": False, "status": fr.get("status")}
    ck = f"imd:insat:maparea:{fr.get('image_time') or len(body)}"
    hit = cache.get(ck)
    if isinstance(hit, dict):
        return hit
    res = await asyncio.to_thread(map_area_jpeg, body)
    if not res:
        return {"ok": False, "status": "decode"}
    jpg, b = res
    out = {"ok": True, "jpeg": jpg, "bounds": b, "image_time": fr.get("image_time"), "source_url": fr.get("url")}
    cache.set(ck, out, 1800)
    return out


def _valid_median(gray, mask, x0: int, x1: int, y0: int, y1: int) -> float | None:
    import numpy as np

    win = gray[y0:y1, x0:x1]
    ok = ~mask[y0:y1, x0:x1]
    vals = win[ok]
    if vals.size == 0:
        return None
    return float(np.median(vals))


def _sample_gray(png: bytes, lat: float, lon: float) -> dict[str, Any] | None:
    rgb = _decode(png)
    if rgb is None:
        return None
    import numpy as np

    h, w = rgb.shape[:2]
    geo = Georef.for_size(w, h)
    west, east, south, north = geo.bounds()
    if not (west <= lon <= east and south <= lat <= north):
        return {"ok": False, "status": "off_frame", "tb_k": None, "gray": None}
    gray = rgb.astype(np.float32) @ np.array([0.299, 0.587, 0.114], dtype=np.float32)
    mask = _overlay_mask(rgb)
    x, y = geo.px(lat, lon)
    xi, yi = int(round(x)), int(round(y))
    g = _valid_median(gray, mask, max(0, xi - 2), min(w, xi + 3), max(0, yi - 2), min(h, yi + 3))
    if g is None:
        g = _valid_median(gray, mask, max(0, xi - 6), min(w, xi + 7), max(0, yi - 6), min(h, yi + 7))
    if g is None:
        return {"ok": False, "status": "masked", "tb_k": None, "gray": None}
    # 12×12 patch at ~0.18° spacing (pixel pitch ≈ 0.035° lon) for local cell finding
    patch: list[list[float]] = []
    half = 6
    for j in range(-half, half):
        row = []
        for i in range(-half, half):
            plat = lat - j * (2.2 / (2 * half))
            plon = lon + i * (2.2 / (2 * half))
            px, py = geo.px(plat, plon)
            pi, pj = int(round(px)), int(round(py))
            v = _valid_median(gray, mask, max(0, pi - 2), min(w, pi + 3), max(0, pj - 2), min(h, pj + 3))
            row.append(_gray_tb(v) if v is not None else 300.0)
        patch.append(row)
    return {
        "ok": True,
        "status": "ok",
        "tb_k": _gray_tb(g),
        "tb_kind": "gray-proxy",
        "tb_note": GRAY_TB_NOTE,
        "gray": round(g, 1),
        "grid": patch,
        "px": [xi, yi],
        "size": [w, h],
    }


def downsample_india(png: bytes, size: int = 140) -> list[list[float]] | None:
    """Mercator-correct India grid (lat rows north→south, lon cols west→east), overlays masked."""
    rgb = _decode(png)
    if rgb is None:
        return None
    import numpy as np

    h, w = rgb.shape[:2]
    geo = Georef.for_size(w, h)
    gray = rgb.astype(np.float32) @ np.array([0.299, 0.587, 0.114], dtype=np.float32)
    mask = _overlay_mask(rgb)
    iw, ie, iso, ino = INDIA_BOUNDS
    from app.data.india_mask import in_india

    lat_edges = [ino - k / size * (ino - iso) for k in range(size + 1)]
    lon_edges = [iw + k / size * (ie - iw) for k in range(size + 1)]
    xs = [int(round(geo.px(0.0, lo)[0])) for lo in lon_edges]
    ys = [int(round(geo.px(la, 0.0)[1])) for la in lat_edges]
    grid: list[list[float]] = []
    for yy in range(size):
        lat = ino - (yy + 0.5) / size * (ino - iso)
        y0, y1 = max(0, ys[yy]), min(h, max(ys[yy + 1], ys[yy] + 1))
        row = []
        for xx in range(size):
            lon = iw + (xx + 0.5) / size * (ie - iw)
            if not in_india(lat, lon):
                row.append(300.0)
                continue
            x0, x1 = max(0, xs[xx]), min(w, max(xs[xx + 1], xs[xx] + 1))
            v = _valid_median(gray, mask, x0, x1, y0, y1)
            if v is None:  # cell entirely on a drawn line: widen
                v = _valid_median(gray, mask, max(0, x0 - 3), min(w, x1 + 3), max(0, y0 - 3), min(h, y1 + 3))
            row.append(_gray_tb(v) if v is not None else 300.0)
        grid.append(row)
    return grid


def downsample_sector(png: bytes, size: int = 80) -> list[list[float]] | None:
    """Coarse full-sector grid on an equal-angle lat/lon lattice over ASIA_BOUNDS."""
    rgb = _decode(png)
    if rgb is None:
        return None
    import numpy as np

    h, w = rgb.shape[:2]
    geo = Georef.for_size(w, h)
    gray = rgb.astype(np.float32) @ np.array([0.299, 0.587, 0.114], dtype=np.float32)
    mask = _overlay_mask(rgb)
    west, east, south, north = ASIA_BOUNDS
    grid: list[list[float]] = []
    for yy in range(size):
        lat = north - (yy + 0.5) / size * (north - south)
        row = []
        for xx in range(size):
            lon = west + (xx + 0.5) / size * (east - west)
            x, y = geo.px(lat, lon)
            xi, yi = int(round(x)), int(round(y))
            v = _valid_median(gray, mask, max(0, xi - 4), min(w, xi + 5), max(geo.map_top, yi - 4), min(h, yi + 5))
            row.append(_gray_tb(v) if v is not None else 300.0)
        grid.append(row)
    return grid


_JPEG_LOCK = None
_JPEG_TTL_S = 120.0


async def fetch_frame() -> dict[str, Any]:
    """Latest Asia-sector IR JPEG (raw, uncropped) + its valid time. Single-flight, cached 120 s."""
    import asyncio
    from email.utils import parsedate_to_datetime

    global _JPEG_LOCK
    hit = cache.get("imd:insat:frame")
    if isinstance(hit, dict):
        return hit
    if _JPEG_LOCK is None:
        _JPEG_LOCK = asyncio.Lock()
    async with _JPEG_LOCK:
        hit = cache.get("imd:insat:frame")
        if isinstance(hit, dict):
            return hit
        last = "empty"
        for url in IR_URLS:
            try:
                r = await client().get(url, timeout=8.0)
            except Exception as e:
                last = f"error:{type(e).__name__}"
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
            image_time = None
            lm = r.headers.get("last-modified")
            if lm:
                try:
                    image_time = parsedate_to_datetime(lm).isoformat()
                except (TypeError, ValueError):
                    image_time = None
            out = {"body": body, "url": url, "status": "ok", "image_time": image_time}
            cache.set("imd:insat:frame", out, _JPEG_TTL_S)
            return out
        fail = {"body": None, "url": None, "status": last, "image_time": None}
        cache.set("imd:insat:frame", fail, 45)
        return fail


async def fetch_jpeg() -> tuple[bytes | None, str | None, str]:
    """Latest Asia-sector IR JPEG (raw bytes; georeference with Georef.for_size)."""
    fr = await fetch_frame()
    return fr.get("body"), fr.get("url"), fr.get("status") or "empty"


async def fetch_ir(lat: float, lon: float) -> dict[str, Any]:
    ck = f"imd:insat:{round(lat, 2)}:{round(lon, 2)}"
    hit = cache.get(ck)
    if isinstance(hit, dict):
        return hit
    import asyncio

    body, url, last = await fetch_jpeg()
    if body and url:
        sampled = await asyncio.to_thread(_sample_gray, body, lat, lon)
        if sampled:
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
        last = "decode"
    fail = {
        "ok": False,
        "source": "imd-insat-ir1",
        "source_kind": "satellite-ir",
        "status": last,
        "tb_k": None,
        "grid": None,
    }
    cache.set(ck, fail, 45)
    return fail


async def fetch_sector() -> dict[str, Any]:
    """Mercator-correct India IR grid for All-India cell finding, keyed by the image time."""
    import asyncio

    fr = await fetch_frame()
    body = fr.get("body")
    if not body:
        return {"ok": False, "source": "imd-insat-ir1", "status": fr.get("status"), "grid": None, "bounds": INDIA_BOUNDS}
    ck = f"imd:insat:sector:{fr.get('image_time') or len(body)}"
    hit = cache.get(ck)
    if isinstance(hit, dict) and hit.get("grid"):
        return hit
    grid = await asyncio.to_thread(downsample_india, body, 140)
    if not grid:
        fail = {"ok": False, "source": "imd-insat-ir1", "status": "decode", "grid": None, "bounds": INDIA_BOUNDS}
        cache.set(ck, fail, 45)
        return fail
    out = {
        "ok": True,
        "source": "imd-insat-ir1",
        "source_kind": "satellite-ir-gray-proxy",
        "tb_note": GRAY_TB_NOTE,
        "bounds": INDIA_BOUNDS,
        "grid": grid,
        "image_time": fr.get("image_time"),
        "status": "ok",
    }
    cache.set(ck, out, 3600)
    return out


async def _band_body(url: str) -> bytes | None:
    """Shared, cached (120 s) download of one band JPEG. TIR reuses the main frame."""
    if url in IR_URLS:
        return (await fetch_frame()).get("body")

    async def factory() -> bytes | None:
        r = await client().get(url, timeout=8.0)
        if r.status_code >= 400 or len(r.content) < 400 or "html" in (r.headers.get("content-type") or "").lower():
            return b""
        return r.content

    import asyncio

    got = await asyncio.shield(cache.aget(f"imd:band:{url}", factory, ttl_s=_JPEG_TTL_S, swr_s=600))
    return got or None


async def fetch_channels(lat: float, lon: float) -> dict[str, Any]:
    """INSAT imager bands (public JPEG). MOSDAC L1B replaces these when wired."""
    import asyncio

    async def one(name: str, urls: tuple[str, ...]) -> dict[str, Any]:
        for url in urls:
            try:
                body = await _band_body(url)
            except Exception:
                continue
            if not body:
                continue
            sampled = await asyncio.to_thread(_sample_gray, body, lat, lon)
            if not sampled or not sampled.get("ok"):
                continue
            ck = f"imd:band:grid48:{url}:{len(body)}"
            grid = cache.get(ck)
            if grid is None:
                grid = await asyncio.to_thread(downsample_india, body, 48)
                cache.set(ck, grid, 3600)
            return {
                "ok": True,
                "channel": name,
                "url": url,
                "tb_k": sampled.get("tb_k"),
                "gray": sampled.get("gray"),
                "grid": grid,
            }
        return {"ok": False, "channel": name}

    rows = await asyncio.gather(*[one(n, u) for n, u in CHANNELS])
    ok = [r for r in rows if r.get("ok")]
    return {"ok": bool(ok), "n": len(ok), "bands": list(rows), "c": len(CHANNELS)}

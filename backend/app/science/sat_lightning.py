"""Satellite-ESTIMATED lightning likelihood (not detected strikes).

Inputs, all free and real:
* NASA GIBS B13 "clean IR" brightness temperature from Himawari-9 + GOES-East + GOES-West
  (one WMS mosaic request, 0.2°, 50°S–50°N — geostationary limb beyond that is unreliable; Meteosat is not in GIBS, so Europe/Africa/Middle East
  are not covered — reported as coverage gaps).
* Cooling rate between two frames 20 min apart (growing updrafts cool fast).
* Overshooting-top texture: pixel ≥5 K colder than its 7×7 neighbourhood mean while < 215 K.
* Open-Meteo CAPE and lifted index at each candidate 1° box (environment gate).

Score (0..1) is a transparent rule, not a trained probability:
  Tb ≤210 K 0.60 | ≤220 K 0.45 | ≤230 K 0.25 | ≤235 K 0.10
  + 0.15 if cooling ≤ −4 K/10 min (+0.25 if ≤ −8) ; + 0.10 for an overshooting-top texture
  × 0.3 if CAPE < 100 J/kg and LI > −1 (stable) ; × 1.15 if CAPE ≥ 1000 or LI ≤ −2
  category: likely ≥ 0.5, possible ≥ 0.3.
Its *confidence* is the measured success ratio from `validate()` against IMERG (rain ≥ 10 mm/h,
the same lightning proxy the research uses), never the score itself.
"""

from __future__ import annotations

import asyncio
import io
import time
from datetime import datetime, timedelta, timezone
from typing import Any

import numpy as np

from app import cache

UTC = timezone.utc
WMS = "https://gibs.earthdata.nasa.gov/wms/epsg4326/best/wms.cgi"
LAYERS = "GOES-West_ABI_Band13_Clean_Infrared,GOES-East_ABI_Band13_Clean_Infrared,Himawari_AHI_Band13_Clean_Infrared"
SOURCES = ["Himawari-9 AHI B13", "GOES-East ABI B13", "GOES-West ABI B13"]
OM = "https://api.open-meteo.com/v1/forecast"
CK = "satltg:v1"
_LOCK = asyncio.Lock()
_TASK: asyncio.Task | None = None
# India (same box as GIBS IR). Global 50S–50N × 360° mosaics are too big for a 512 MiB API.
INDIA_BBOX = (5.0, 65.0, 38.0, 100.0)
WORLD_BBOX = (-50.0, -180.0, 50.0, 180.0)


def default_bbox() -> tuple[float, float, float, float]:
    from app.config import cloud_light

    return INDIA_BBOX if cloud_light() else WORLD_BBOX


def validate_enabled() -> bool:
    """IMERG skill scoring is research-only and memory-heavy; skip it on cloud."""
    import os

    raw = (os.environ.get("SATLTG_VALIDATE") or "").strip().lower()
    if raw:
        return raw in {"1", "true", "yes", "on"}
    from app.config import cloud_light

    return not cloud_light()


def _tb(png: bytes) -> np.ndarray:
    from PIL import Image

    from app.providers.gibs_ir import _tb_full

    arr = np.asarray(Image.open(io.BytesIO(png)).convert("RGBA"))
    tb = _tb_full(arr)
    tb[arr[..., 3] < 255] = np.nan  # anti-aliased disk edges / seams decode to bogus colours
    return tb


async def tb_mosaic(t: str, bbox: tuple[float, float, float, float], res: float) -> np.ndarray | None:
    """Tb (K) [lat desc, lon asc] for bbox (s, w, n, e) at `res` degrees; NaN = no satellite."""
    from app.providers.http import client

    s, w, n, e = bbox
    W, H = int(round((e - w) / res)), int(round((n - s) / res))
    key = f"satltg:tb:{t}:{bbox}:{res}"
    hit = cache.get(key)
    if isinstance(hit, np.ndarray):
        return hit
    r = await client().get(
        WMS,
        params={"SERVICE": "WMS", "REQUEST": "GetMap", "VERSION": "1.3.0", "LAYERS": LAYERS, "CRS": "EPSG:4326",
                "BBOX": f"{s},{w},{n},{e}", "WIDTH": str(W), "HEIGHT": str(H), "FORMAT": "image/png",
                "TRANSPARENT": "TRUE", "TIME": t},
        timeout=60.0,
    )
    if r.status_code >= 400 or "image" not in (r.headers.get("content-type") or ""):
        return None
    tb = await asyncio.to_thread(_tb, r.content)
    if not np.isfinite(tb).any():
        return None
    cache.set(key, tb, 3 * 3600)
    return tb


def _win(a: np.ndarray, k: int, fn) -> np.ndarray:
    p = k // 2
    pad = np.pad(a, p, mode="edge")
    v = np.lib.stride_tricks.sliding_window_view(pad, (k, k))
    with np.errstate(all="ignore"):
        return fn(v, axis=(-2, -1))


def _median3(a: np.ndarray) -> np.ndarray:
    import warnings

    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        return _win(a, 3, np.nanmedian)


def score(tb: np.ndarray, tb_prev: np.ndarray | None, dt_min: float) -> dict[str, np.ndarray]:
    """Per-pixel score before the environment gate. Both frames are 3×3-median filtered first:
    WMS colour palettes decode with isolated speckle (single bogus ~195 K pixels)."""
    tb = _median3(tb)
    tb_prev = _median3(tb_prev) if tb_prev is not None else None
    with np.errstate(invalid="ignore"):
        base = np.where(tb <= 210, 0.60, np.where(tb <= 220, 0.45, np.where(tb <= 230, 0.25, np.where(tb <= 235, 0.10, 0.0))))
        cool = np.full(tb.shape, np.nan, np.float32)
        if tb_prev is not None and dt_min > 0:
            # Advection tolerance: compare with the coldest previous pixel in a 3×3 window
            # (cooling = current colder than anything nearby 20 min ago).
            prev_min = _win(np.where(np.isfinite(tb_prev), tb_prev, 330.0), 3, np.min)
            prev_min = np.where(prev_min >= 330.0, np.nan, prev_min)  # no previous data ≠ cooling
            cool = (tb - prev_min) / dt_min * 10.0  # K per 10 min (negative = cooling)
        add = np.where(cool <= -8, 0.25, np.where(cool <= -4, 0.15, 0.0))
        import warnings

        with warnings.catch_warnings():
            warnings.simplefilter("ignore", RuntimeWarning)
            mean7 = _win(tb, 7, np.nanmean)
        ot = (tb < 215) & (tb <= mean7 - 5)
        p = np.where(base > 0, base + add + np.where(ot, 0.10, 0.0), 0.0)
    return {"p": np.nan_to_num(p).astype(np.float32), "cool": cool, "ot": ot}


async def env_at(points: list[tuple[float, float]], when: datetime) -> list[dict[str, float | None]]:
    """CAPE / lifted index at each point for hour `when` (Open-Meteo, one batched request)."""
    from app.providers.http import client

    out: list[dict[str, float | None]] = [{} for _ in points]
    todo = []
    hk = when.strftime("%Y-%m-%dT%H:00")
    for i, (la, lo) in enumerate(points):
        hit = cache.get(f"satltg:env:{round(la)}:{round(lo)}:{hk}")
        if isinstance(hit, dict):
            out[i] = hit
        else:
            todo.append(i)
    for k in range(0, len(todo), 50):
        chunk = todo[k:k + 50]
        try:
            r = await client().get(
                OM,
                params={"latitude": ",".join(f"{points[i][0]:.2f}" for i in chunk),
                        "longitude": ",".join(f"{points[i][1]:.2f}" for i in chunk),
                        "hourly": "cape,lifted_index", "past_days": 1, "forecast_days": 1, "timezone": "GMT"},
                timeout=30.0,
            )
            if r.status_code >= 400:
                continue
            body = r.json()
            rows = body if isinstance(body, list) else [body]
        except Exception:  # noqa: BLE001
            continue
        for i, row in zip(chunk, rows):
            h = row.get("hourly") or {}
            times = h.get("time") or []
            j = times.index(hk) if hk in times else None
            v = {"cape": None, "li": None}
            if j is not None:
                v = {"cape": (h.get("cape") or [None])[j], "li": (h.get("lifted_index") or [None])[j]}
            out[i] = v
            la, lo = points[i]
            cache.set(f"satltg:env:{round(la)}:{round(lo)}:{hk}", v, 2 * 3600)
    return out


def _gate(p: float, cape: float | None, li: float | None) -> float:
    if cape is None and li is None:
        return p
    if (cape is not None and cape < 100) and (li is None or li > -1):
        return p * 0.3  # stable column: cold tops are most likely cirrus / frontal cloud
    if (cape is not None and cape >= 1000) or (li is not None and li <= -2):
        return min(0.95, p * 1.15)
    return p


def boxes(sc: dict[str, np.ndarray], tb: np.ndarray, bbox, res: float, k: int, thr: float = 0.3, cap: int = 400):
    """Pool to k×k-pixel boxes; candidate boxes (max score ≥ thr) strongest first."""
    s, w, n, e = bbox
    H, W = tb.shape
    hh, ww = (H // k) * k, (W // k) * k
    P = sc["p"][:hh, :ww].reshape(hh // k, k, ww // k, k).max((1, 3))
    # ≥3 pixels ≤220 K in the box: single cold pixels are colour-decoding / seam noise.
    C = (np.nan_to_num(tb, nan=330.0)[:hh, :ww] <= 220).reshape(hh // k, k, ww // k, k).sum((1, 3))
    iy, ix = np.where((P >= thr) & (C >= 3))
    out = []
    for y, x in zip(iy, ix):
        blk = (slice(y * k, (y + 1) * k), slice(x * k, (x + 1) * k))
        with np.errstate(all="ignore"):
            out.append({
                "lat": round(float(n - (y + 0.5) * k * res), 2),
                "lon": round(float(w + (x + 0.5) * k * res), 2),
                "score_ir": round(float(P[y, x]), 3),
                "min_tb_k": round(float(np.nanmin(tb[blk])), 1),
                "cool_k_10min": None if not np.isfinite(sc["cool"][blk]).any() else round(float(np.nanmin(sc["cool"][blk])), 1),
                "ot": bool(sc["ot"][blk].any()),
                "cold_px": int((tb[blk] <= 220).sum()),
                "_yx": (int(y), int(x)),
            })
    out.sort(key=lambda c: -c["score_ir"])
    return out[:cap], P


def _full_cover(bbox) -> float:
    """Expected finite fraction with all three disks present (no Meteosat → ~0.80 globally)."""
    s, w, n, e = bbox
    return 0.80 if (e - w) >= 300 else 0.95


def _times(now: datetime | None = None) -> list[datetime]:
    now = now or datetime.now(UTC)
    base = now - timedelta(minutes=30)
    base = base.replace(minute=base.minute - base.minute % 10, second=0, microsecond=0)
    return [base - timedelta(minutes=10 * k) for k in range(7)]


async def _pair(t_candidates: list[datetime], bbox, res):
    for t in t_candidates:
        cur = await tb_mosaic(t.strftime("%Y-%m-%dT%H:%M:%SZ"), bbox, res)
        # Each satellite reaches GIBS with its own delay: a frame where only some of the
        # three disks have arrived would make fake "cooling" at disk borders.
        if cur is None or float(np.isfinite(cur).mean()) < 0.92 * _full_cover(bbox):
            continue
        prev = await tb_mosaic((t - timedelta(minutes=20)).strftime("%Y-%m-%dT%H:%M:%SZ"), bbox, res)
        return t, cur, prev
    return None, None, None


async def estimate(bbox=None, res: float = 0.2, k: int = 5, when: datetime | None = None) -> dict[str, Any]:
    bbox = tuple(bbox) if bbox is not None else default_bbox()
    t, cur, prev = await _pair(_times(when), bbox, res)
    if cur is None:
        return {"ok": False, "status": "no_ir_frame", "bbox": bbox}
    sc = await asyncio.to_thread(score, cur, prev, 20.0)
    cand, _ = await asyncio.to_thread(boxes, sc, cur, bbox, res, k)
    # 10°W–60°E is either the extreme GOES-East limb or uncovered (no Meteosat in GIBS).
    cand = [c for c in cand if not (-10.0 < c["lon"] < 60.0)]
    top = cand[:120]
    env = await env_at([(c["lat"], c["lon"]) for c in top], t)
    cells = []
    for c, ev in zip(top, env):
        p = _gate(c["score_ir"], ev.get("cape"), ev.get("li"))
        if p < 0.3:
            continue
        c.pop("_yx", None)
        cells.append({**c, "cape": ev.get("cape"), "li": ev.get("li"), "score": round(p, 3),
                      "category": "likely" if p >= 0.5 else "possible"})
    cover = float(np.isfinite(cur).mean())
    prev_iso = (t - timedelta(minutes=20)).isoformat() if prev is not None else None
    # Free the mosaics before we return; they can be tens of MiB globally.
    del cur, prev, sc
    return {
        "ok": True,
        "kind": "satellite-estimated lightning likelihood (not detected strikes)",
        "valid": t.isoformat(),
        "prev_frame": prev_iso,
        "sources": SOURCES + ["Open-Meteo CAPE / lifted index"],
        "coverage_frac": round(cover, 3),
        "coverage_note": "No Meteosat in NASA GIBS: Europe, Africa, the Middle East and the Atlantic east of ~30°W are not covered.",
        "bbox": bbox,
        "res_deg": res * k,
        "n_candidates": len(cand),
        "cells": cells,
        "rule": "Tb≤220 K cold tops (+20-min cooling, +overshooting-top texture) × CAPE/LI gate; likely ≥0.5, possible ≥0.3",
    }


def _score_tbl(pred: np.ndarray, obs: np.ndarray) -> dict[str, Any]:
    tp = int((pred & obs).sum()); fp = int((pred & ~obs).sum()); fn = int((~pred & obs).sum())
    return {"hits": tp, "false_alarms": fp, "misses": fn,
            "pod": round(tp / (tp + fn), 3) if tp + fn else None,
            "far": round(fp / (tp + fp), 3) if tp + fp else None,
            "sr": round(tp / (tp + fp), 3) if tp + fp else None,
            "csi": round(tp / (tp + fp + fn), 3) if tp + fp + fn else None}


async def validate(n_hours: int = 3) -> dict[str, Any]:
    """Score the IR rule (at H:30 with the H:10 frame for cooling) against IMERG Early hour H
    (≥10 mm/h, 0.5° boxes) over the PN-Net India domain, for the newest `n_hours` hours.
    The CAPE/LI gate uses the same hour. Real data only; small samples are reported as such."""
    from app.science.pn import live as pn_live

    obs = await pn_live.observed_hours(n_hours)
    if not obs["hours"]:
        return {"ok": False, "status": "no_imerg", "errors": obs.get("errors")}
    s, n = float(pn_live.LAT[0] - 0.05), float(pn_live.LAT[-1] + 0.05)
    w, e = float(pn_live.LON[0] - 0.05), float(pn_live.LON[-1] + 0.05)
    bbox = (round(s, 2), round(w, 2), round(n, 2), round(e, 2))
    tot = {"likely": np.zeros(3, int), "possible": np.zeros(3, int), "ir_only_220": np.zeros(3, int)}
    per = []
    for h, rain in zip(obs["hours"], obs["rain"]):
        t = h + timedelta(minutes=30)
        cur = await tb_mosaic(t.strftime("%Y-%m-%dT%H:%M:%SZ"), bbox, 0.1)
        prev = await tb_mosaic((t - timedelta(minutes=20)).strftime("%Y-%m-%dT%H:%M:%SZ"), bbox, 0.1)
        if cur is None:
            per.append({"hour": h.isoformat(), "status": "no_ir"})
            continue
        cur = cur[::-1][: pn_live.H, : pn_live.W]  # north-first → south-first like IMERG
        prev = prev[::-1][: pn_live.H, : pn_live.W] if prev is not None else None
        sc = await asyncio.to_thread(score, cur, prev, 20.0)  # keep the event loop free
        k = 5
        hh, ww = (pn_live.H // k) * k, (pn_live.W // k) * k
        P = sc["p"][:hh, :ww].reshape(hh // k, k, ww // k, k).max((1, 3))
        ir220 = (np.nan_to_num(cur, nan=330)[:hh, :ww] <= 220).reshape(hh // k, k, ww // k, k).any((1, 3))
        ob = (rain[:hh, :ww] >= 10.0).reshape(hh // k, k, ww // k, k).any((1, 3))
        iy, ix = np.where(P >= 0.3)
        pts = [(float(pn_live.LAT[y * k + 2]), float(pn_live.LON[x * k + 2])) for y, x in zip(iy, ix)]
        env = await env_at(pts, h) if pts else []
        G = np.zeros_like(P)
        for (y, x), ev in zip(zip(iy, ix), env):
            G[y, x] = _gate(float(P[y, x]), ev.get("cape"), ev.get("li"))
        row = {"hour": h.isoformat(), "ir_valid": t.isoformat(), "obs_boxes": int(ob.sum())}
        for name, pred in (("likely", G >= 0.5), ("possible", G >= 0.3), ("ir_only_220", ir220)):
            sres = _score_tbl(pred, ob)
            row[name] = sres
            tot[name] += np.array([sres["hits"], sres["false_alarms"], sres["misses"]])
        per.append(row)
    summary = {}
    for name, (tp, fp, fn) in tot.items():
        summary[name] = {"hits": int(tp), "false_alarms": int(fp), "misses": int(fn),
                         "pod": round(tp / (tp + fn), 3) if tp + fn else None,
                         "far": round(fp / (tp + fp), 3) if tp + fp else None,
                         "csi": round(tp / (tp + fp + fn), 3) if tp + fp + fn else None}
    return {"ok": True, "truth": "IMERG Early ≥10 mm/h (research lightning proxy), 0.5° boxes, India domain",
            "strike_truth": "none available (Weatherbit key rejected; no free strike feed)",
            "hours": per, "total": summary}


async def refresh() -> dict[str, Any]:
    from app.heavy import slot

    async with slot():
        async with _LOCK:
            hit = cache.get(CK)
            if isinstance(hit, dict) and time.time() - float(hit.get("_ts", 0)) < 15 * 60:
                return hit
            try:
                pack = await estimate()
            except Exception as e:  # noqa: BLE001
                pack = {"ok": False, "status": "error", "error": str(e)[:200]}
            val = cache.get(CK + ":val")
            if validate_enabled() and (
                not isinstance(val, dict) or time.time() - float(val.get("_ts", 0)) > 3600
            ):
                try:
                    val = await validate(3)
                except Exception as e:  # noqa: BLE001
                    val = {"ok": False, "status": "error", "error": str(e)[:200]}
                val["_ts"] = time.time()
                cache.set(CK + ":val", val, 6 * 3600)
            elif not isinstance(val, dict):
                val = {"ok": False, "status": "skipped_on_cloud"}
            tot = (val or {}).get("total") or {}
            pack["validation"] = {k: v for k, v in (val or {}).items() if not k.startswith("_")}
            # Confidence shown to users = measured success ratio (1 − FAR) of the 'likely' class.
            lk = tot.get("likely") or {}
            pack["confidence"] = None if lk.get("far") is None else round(1 - lk["far"], 3)
            pack["_ts"] = time.time()
            cache.set(CK, pack, 3 * 3600)
            if pack.get("ok"):
                try:
                    from app.store import shared_packs

                    shared_packs.save_lightning(pack)
                except Exception:
                    pass
            return pack


def _from_mongo() -> dict[str, Any] | None:
    try:
        from app.store import shared_packs

        hit = shared_packs.load_lightning()
    except Exception:
        return None
    if isinstance(hit, dict) and hit.get("ok"):
        if "_ts" not in hit:
            hit = dict(hit)
            hit["_ts"] = float(hit.get("saved_at") or time.time())
        cache.set(CK, hit, 15 * 60)
        return hit
    return None


def peek(kick: bool = True) -> dict[str, Any] | None:
    global _TASK
    hit = cache.get(CK)
    if not isinstance(hit, dict):
        hit = cache.peek(CK)
    if not isinstance(hit, dict):
        hit = _from_mongo()
    fresh = isinstance(hit, dict) and time.time() - float(hit.get("_ts") or hit.get("saved_at") or 0) < 15 * 60
    if kick and not fresh and (_TASK is None or _TASK.done()):
        # On cloud, a slightly stale ingest pack is enough — do not start a mosaic here.
        if isinstance(hit, dict) and hit.get("ok"):
            try:
                from app.config import cloud_light

                if cloud_light():
                    return hit
            except Exception:
                pass
        try:
            _TASK = asyncio.get_running_loop().create_task(refresh())
        except RuntimeError:
            pass
    return hit if isinstance(hit, dict) else None

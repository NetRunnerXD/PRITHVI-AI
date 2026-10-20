"""PN-Net v4 live run on real IMERG Early (GPM_3IMERGHHE, 30-min, 0.1°).

Input exactly as in research `build_dataset_v4.py` / `train_nowcast_v4.py`:
  hour h = mean of the h:00 and h:30 half-hours (mm/h), domain = IMERG index lat 949..1268,
  lon 2449..2796 (320×348, south row first), model input = log1p(mm/h) for the last 4 hours.
  Lead L (1..12) is the hour starting at (last input hour + L).

Honesty rules:
* IMERG Early arrives ~4 h late, so the first leads are already in the past when we run.
  Every lead carries `valid_start` and `lead_from_now_min` (negative = already past).
* INSAT / ERA5-env / IFS groups are passed with availability mask 0 (as in training when
  missing). NWP latency rule if/when wired: GFS run ≤ T−6 h, IFS run ≤ T−8 h.
* If the newest complete IMERG hour is older than PN_STALE_OBS_H (default 6 h) the model is
  NOT run; the pack falls back to persistence of the last observed hour and says so.
* Validation: a second run with the input window ending 3 h earlier is scored against the
  3 observed hours that followed (same IMERG product) — real data only.
"""

from __future__ import annotations

import asyncio
import os
import time
from datetime import datetime, timedelta, timezone
from typing import Any

import numpy as np

from app import cache

UTC = timezone.utc
LAT0, LON0, H, W = 949, 2449, 320, 348
LAT = -89.95 + 0.1 * np.arange(LAT0, LAT0 + H)
LON = -179.95 + 0.1 * np.arange(LON0, LON0 + W)
CMR = "https://cmr.earthdata.nasa.gov/search/granules.json"
OPENDAP = "https://gpm1.gesdisc.eosdis.nasa.gov/opendap/"
CK = "pn:live:v1"
_LOCK = asyncio.Lock()
_TASK: asyncio.Task | None = None


def stale_h() -> float:
    try:
        return max(1.0, float(os.environ.get("PN_STALE_OBS_H") or 6))
    except ValueError:
        return 6.0


async def _granules(n: int = 24) -> list[dict[str, Any]]:
    from app.providers.gpm_imerg import _headers
    from app.providers.http import client

    r = await client().get(
        CMR,
        params={"short_name": "GPM_3IMERGHHE", "version": "07", "page_size": n, "sort_key": "-start_date"},
        headers={**_headers(), "Accept": "application/json"},
        timeout=30.0,
    )
    r.raise_for_status()
    out = []
    for e in ((r.json().get("feed") or {}).get("entry") or []):
        hrefs = [lk.get("href") for lk in (e.get("links") or []) if isinstance(lk, dict) and lk.get("href")]
        href = next((h for h in hrefs if str(h).endswith(".HDF5") and "data.gesdisc" in str(h)), None)
        if not href:
            continue
        t = datetime.fromisoformat(str(e.get("time_start")).replace("Z", "+00:00"))
        out.append({"t": t, "href": href})
    return sorted(out, key=lambda g: g["t"])


def _parse_ascii(text: str) -> np.ndarray | None:
    """Hyrax DAP2 ASCII for precipitation[0][lon][lat] → array [lat, lon] (south first)."""
    rows: list[list[float]] = []
    for line in text.splitlines():
        line = line.strip()
        if not line.startswith("[0]["):
            continue
        parts = line.split(",")
        try:
            rows.append([float(x) for x in parts[1:]])
        except ValueError:
            continue
    if len(rows) != W or any(len(r) != H for r in rows):
        return None
    a = np.asarray(rows, np.float32).T  # [lat, lon]
    a[(a < 0) | (a > 500)] = np.nan
    return a


async def _frame(href: str) -> np.ndarray | None:
    from app.providers.gpm_imerg import _headers
    from app.providers.http import client

    key = f"pn:hhr:{href.rsplit('/', 1)[-1]}"
    hit = cache.get(key)
    if isinstance(hit, np.ndarray):
        return hit
    base = href.replace("https://data.gesdisc.earthdata.nasa.gov/data/", OPENDAP)
    ce = f"precipitation[0:1:0][{LON0}:1:{LON0 + W - 1}][{LAT0}:1:{LAT0 + H - 1}]"
    r = await client().get(f"{base}.ascii?{ce}", headers=_headers(), timeout=90.0)
    if r.status_code >= 400:
        raise RuntimeError(f"opendap http_{r.status_code}")
    a = _parse_ascii(r.text)
    if a is not None:
        cache.set(key, a, 6 * 3600)
    return a


async def observed_hours(n_hours: int = 7) -> dict[str, Any]:
    """Newest `n_hours` complete hourly means (oldest first)."""
    gs = await _granules(2 * n_hours + 6)
    by_t = {g["t"]: g for g in gs}
    hours = sorted({g["t"].replace(minute=0) for g in gs if g["t"].minute == 0 and (g["t"] + timedelta(minutes=30)) in by_t})
    hours = hours[-n_hours:]
    sem = asyncio.Semaphore(4)

    async def one(t):
        async with sem:
            return await _frame(by_t[t]["href"])

    ts = [t for h in hours for t in (h, h + timedelta(minutes=30))]
    frames = await asyncio.gather(*(one(t) for t in ts), return_exceptions=True)
    out_h, out_a = [], []
    for k, h in enumerate(hours):
        a, b = frames[2 * k], frames[2 * k + 1]
        if isinstance(a, np.ndarray) and isinstance(b, np.ndarray):
            m = 0.5 * (a + b)
            if np.isfinite(m).mean() > 0.9:
                out_h.append(h)
                out_a.append(np.nan_to_num(np.maximum(m, 0)))
    errs = [str(f)[:120] for f in frames if isinstance(f, BaseException)]
    return {"hours": out_h, "rain": out_a, "errors": errs[:3]}


def _score(pred: np.ndarray, obs: np.ndarray) -> dict[str, Any]:
    tp = int((pred & obs).sum()); fp = int((pred & ~obs).sum()); fn = int((~pred & obs).sum())
    return {
        "hits": tp, "false_alarms": fp, "misses": fn,
        "sr": round(tp / (tp + fp), 3) if tp + fp else None,
        "pod": round(tp / (tp + fn), 3) if tp + fn else None,
        "csi": round(tp / (tp + fp + fn), 3) if tp + fp + fn else None,
    }


def _cells(mask: np.ndarray, prob: np.ndarray, cap: int = 150) -> list[dict[str, Any]]:
    """Event pixels pooled to 0.5° boxes (research verification scale), strongest first."""
    out = []
    for i in range(0, H, 5):
        for j in range(0, W, 5):
            blk = mask[i:i + 5, j:j + 5]
            if blk.any():
                p = float(prob[i:i + 5, j:j + 5].max())
                out.append({"lat": round(float(LAT[i:i + 5].mean()), 2), "lon": round(float(LON[j:j + 5].mean()), 2), "p": round(p, 3), "px": int(blk.sum())})
    out.sort(key=lambda c: -c["p"])
    return out[:cap]


def _pool(a: np.ndarray, k: int = 5) -> np.ndarray:
    hh, ww = (H // k) * k, (W // k) * k
    return a[:hh, :ww].reshape(hh // k, k, ww // k, k).max((1, 3))


def _build(obs: dict[str, Any]) -> dict[str, Any]:
    from app.science.pn import net, params

    now = datetime.now(UTC)
    hours, rain = obs["hours"], obs["rain"]
    base: dict[str, Any] = {
        "model": "PN-Net v4 (ConvLSTM, ONNX CPU)",
        "input": "IMERG Early half-hourly → hourly mean, last 4 h, 0.1°, India domain 4.95–36.85°N 64.95–99.65°E",
        "groups_masked": ["insat", "env", "nwp"],
        "nwp_latency_rule": "GFS run ≤ T−6 h, IFS run ≤ T−8 h (NWP group not wired live → masked)",
        "label_note": "Lightning head = research proxy: rain ≥10 mm/h (or TIR1<215 K at lead 1 when INSAT present).",
        "generated": now.isoformat(),
        "errors": obs.get("errors") or [],
    }
    if len(hours) < 4:
        return {**base, "ok": False, "status": "insufficient_imerg", "n_hours": len(hours)}
    last = hours[-1]
    age_h = (now - (last + timedelta(hours=1))).total_seconds() / 3600
    base.update({"last_obs_hour": last.isoformat(), "obs_age_h": round(age_h, 2)})
    if age_h > stale_h():
        pers = rain[-1]
        return {
            **base, "ok": True, "status": "persistence_fallback",
            "note": f"Newest IMERG hour is {age_h:.1f} h old (> PN_STALE_OBS_H={stale_h():g}); PN-Net not run. Persistence of the last observed hour.",
            "persistence_cells": _cells(pers >= 10.0, np.minimum(pers / 20.0, 1.0)),
        }
    cal = params()["pn_net_v4"]["calibration"]
    t0 = time.time()
    r = net.run(np.stack(rain[-4:]))
    run_ms = round((time.time() - t0) * 1000)
    if not r.get("ok"):
        return {**base, "ok": False, "status": r.get("status"), "needs": r.get("needs")}
    skill = (params().get("skill") or {}).get("pn_net_ltg_0p5", {}).get("by_lead_h", {})
    leads = []
    for L in range(12):
        vs = last + timedelta(hours=L + 1)
        lead_now = round((vs - now).total_seconds() / 60)
        sk = skill.get(str(L + 1)) or {}
        leads.append({
            "lead_h": L + 1,
            "valid_start": vs.isoformat(),
            "lead_from_now_min": lead_now,
            "past": lead_now < 0,
            "ltg_cut": cal["ltg"]["cut"][L],
            "n_ltg_px": int(r["ltg_event"][L].sum()),
            "n_rain_px": int(r["rain_event"][L].sum()),
            "max_mm_h": round(float(r["mm_h"][L].max()), 1),
            "skill_sr": sk.get("sr"),
            "ltg_cells": _cells(r["ltg_event"][L], r["p_ltg"][L], 60) if lead_now >= -60 else [],
        })
    # Live validation: rerun with the window ending 3 h earlier and score leads 1..3 against
    # the observed hours that followed (0.5° max-pooled, as in the research verification).
    val = None
    if len(rain) >= 7:
        rv = net.run(np.stack(rain[-7:-3]))
        if rv.get("ok"):
            val = {"input_end_hour": hours[-4].isoformat(), "by_lead": []}
            for L in range(3):
                ob = rain[-3 + L]
                val["by_lead"].append({
                    "lead_h": L + 1,
                    "valid_start": hours[-3 + L].isoformat(),
                    "lightning_proxy_0p5": _score(_pool(rv["ltg_event"][L]), _pool(ob >= 10.0)),
                    "rain_ge1_0p5": _score(_pool(rv["rain_event"][L]), _pool(ob >= 1.0)),
                    "persistence_rain_ge1_0p5": _score(_pool(rain[-4] >= 1.0), _pool(ob >= 1.0)),
                })
    return {**base, "ok": True, "status": "ok", "run_ms": run_ms, "input_hours": [h.isoformat() for h in hours[-4:]], "leads": leads, "validation": val}


async def refresh() -> dict[str, Any]:
    async with _LOCK:
        hit = cache.get(CK)
        if isinstance(hit, dict) and time.time() - float(hit.get("_ts", 0)) < 20 * 60:
            return hit
        try:
            obs = await observed_hours(7)
            pack = await asyncio.to_thread(_build, obs)
        except Exception as e:  # noqa: BLE001
            pack = {"ok": False, "status": "error", "error": str(e)[:200]}
        pack["_ts"] = time.time()
        cache.set(CK, pack, 3 * 3600)
        return pack


def peek(kick: bool = True) -> dict[str, Any] | None:
    """Cached pack without blocking; optionally start a background refresh."""
    global _TASK
    from app.science.pn import net

    if not net.status().get("enabled"):
        return None
    hit = cache.get(CK)
    fresh = isinstance(hit, dict) and time.time() - float(hit.get("_ts", 0)) < 20 * 60
    if kick and not fresh and (_TASK is None or _TASK.done()):
        try:
            _TASK = asyncio.get_running_loop().create_task(refresh())
        except RuntimeError:
            pass
    return hit if isinstance(hit, dict) else None

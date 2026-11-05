"""PN live run on real IMERG Early (GPM_3IMERGHHE, 30-min, 0.1°).

PN_VERSION selects the engine (PN_ENABLED=1 required for both):
  v4 (default)  PN-Net v4 ConvLSTM, IMERG only (below)
  v7            PRITHVI-Nowcast v7 final system (R2 + PN-Blend), IMERG + live GFS/IFS rain and
                environment with the training latency rule; INSAT masked. See _build_v7.
Fallbacks: v7 → persistence when IMERG is stale; v4 stays selectable by env.

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
CK7 = "pn:live:v7"
_LOCK = asyncio.Lock()
_TASK: asyncio.Task | None = None


def stale_h() -> float:
    try:
        return max(1.0, float(os.environ.get("PN_STALE_OBS_H") or 6))
    except ValueError:
        return 6.0


async def _granules(n: int = 24) -> list[dict[str, Any]]:
    from app.providers.http import client

    r = await client().get(
        CMR,
        params={"short_name": "GPM_3IMERGHHE", "version": "07", "page_size": n, "sort_key": "-start_date"},
        headers={"Accept": "application/json"},  # CMR search is public; no token sent
        timeout=60.0,
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


def _parse_ascii(text: str, h: int = H, w: int = W) -> np.ndarray | None:
    """Hyrax DAP2 ASCII for precipitation[0][lon][lat] → array [lat, lon] (south first)."""
    import re

    rows: list[list[float]] = []
    row_re = re.compile(r"^(?:\w+)?\[0\]\[\d+\],")  # "precipitation[0][j], v, v, ..."
    for line in text.splitlines():
        line = line.strip()
        if not row_re.match(line):
            continue
        parts = line.split(",")
        try:
            rows.append([float(x) for x in parts[1:]])
        except ValueError:
            continue
    if len(rows) != w or any(len(r) != h for r in rows):
        return None
    a = np.asarray(rows, np.float32).T  # [lat, lon]
    a[(a < 0) | (a > 500)] = np.nan
    return a


async def _frame(href: str, h: int = H, w: int = W) -> np.ndarray | None:
    from app.providers.gpm_imerg import _headers
    from app.providers.http import client

    key = f"pn:hhr:{href.rsplit('/', 1)[-1]}" + ("" if (h, w) == (H, W) else f":{h}x{w}")
    hit = cache.get(key)
    if isinstance(hit, np.ndarray):
        return hit
    base = href.replace("https://data.gesdisc.earthdata.nasa.gov/data/", OPENDAP)
    ce = f"precipitation[0:1:0][{LON0}:1:{LON0 + w - 1}][{LAT0}:1:{LAT0 + h - 1}]"
    r = await client().get(f"{base}.ascii?{ce}", headers=_headers(), timeout=90.0)
    if r.status_code >= 400:
        raise RuntimeError(f"opendap http_{r.status_code}")
    a = _parse_ascii(r.text, h, w)
    if a is None:
        ct = r.headers.get("content-type", "")
        raise RuntimeError(f"opendap unparsable ({ct[:40]}, {len(r.text)} chars)")
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
    return {"hours": out_h, "rain": out_a, "errors": errs[:3], "hrefs": {t: g["href"] for t, g in by_t.items()}}


async def hours_ext(obs: dict[str, Any], hours: list[datetime], h: int, w: int) -> list[np.ndarray | None]:
    """Hourly means (NaN kept, unclipped) on a larger tile from the same origin — PN-Correct uses 331×351
    (the research IMERG archive tile). None where a half-hour is missing."""
    hrefs = obs.get("hrefs") or {}

    async def one(hr: datetime) -> np.ndarray | None:
        a_t, b_t = hr, hr + timedelta(minutes=30)
        if a_t not in hrefs or b_t not in hrefs:
            return None
        try:
            a, b = await asyncio.gather(_frame(hrefs[a_t], h, w), _frame(hrefs[b_t], h, w))
        except Exception:  # noqa: BLE001
            return None
        return 0.5 * (a + b) if isinstance(a, np.ndarray) and isinstance(b, np.ndarray) else None

    return [await one(hr) for hr in hours]


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


def _v7() -> bool:
    from app.science.pn import v7

    return v7.version() == "v7"


def engine_status() -> dict[str, Any]:
    """Status of the selected engine (PN_VERSION=v7 → v7, else v4)."""
    from app.science.pn import net, v7

    return v7.status() if _v7() else net.status()


def _ck() -> str:
    return CK7 if _v7() else CK


async def _refresh_v7() -> dict[str, Any]:
    from app.science.pn import nwp_v7, v7

    obs = await observed_hours(9)
    hours = obs["hours"]
    nwp = nwp_val = None
    if hours:
        t_issue = (hours[-1] + timedelta(hours=1)).replace(tzinfo=None)
        norm = v7.cfg()["norm_nenv"]
        try:
            import eccodes  # noqa: F401

            nwp = await nwp_v7.build(t_issue, norm)
            if len(hours) >= 9:
                nwp_val = await nwp_v7.build(t_issue - timedelta(hours=3), norm)
        except ImportError:
            pass
        except Exception as e:  # noqa: BLE001 — NWP trouble masks the groups, never blocks the nowcast
            obs.setdefault("errors", []).append(f"nwp: {str(e)[:100]}")
    pnc = None
    if hours:
        try:
            pnc = await _pnc_inputs(obs, (hours[-1] + timedelta(hours=1)).replace(tzinfo=None))
        except Exception as e:  # noqa: BLE001 — PN-Correct trouble never blocks the v7 nowcast
            pnc = {"error": str(e)[:120]}
    return await asyncio.to_thread(_build_v7, obs, nwp, nwp_val, pnc)


async def _pnc_inputs(obs: dict[str, Any], T: datetime) -> dict[str, Any] | None:
    """PN-Correct inputs (only when PN_CORRECT_ENABLED=1): primary GFS/IFS runs + IMERG T−1..T−3 on 331×351."""
    from app.science.pn import correct, hooks, nwp_v7

    if not (hooks.correct_enabled() and correct.status()["enabled"]):
        return None
    try:
        import eccodes  # noqa: F401
    except ImportError:
        return {"error": "eccodes missing"}
    inp = await nwp_v7.build_correct_runs(T)
    tz = obs["hours"][-1].tzinfo
    inp["obs"] = await hours_ext(obs, [(T - timedelta(hours=k + 1)).replace(tzinfo=tz) for k in range(3)], correct.OBS_H, correct.OBS_W)
    return inp


async def refresh() -> dict[str, Any]:
    async with _LOCK:
        ck = _ck()
        hit = cache.get(ck)
        if isinstance(hit, dict) and time.time() - float(hit.get("_ts", 0)) < 20 * 60:
            return hit
        try:
            if _v7():
                pack = await _refresh_v7()
            else:
                obs = await observed_hours(7)
                pack = await asyncio.to_thread(_build, obs)
        except Exception as e:  # noqa: BLE001
            pack = {"ok": False, "status": "error", "error": str(e)[:200]}
        pack["_ts"] = time.time()
        cache.set(ck, pack, 3 * 3600)
        return pack


def peek(kick: bool = True) -> dict[str, Any] | None:
    """Cached pack without blocking; optionally start a background refresh."""
    global _TASK

    if not engine_status().get("enabled"):
        return None
    hit = cache.get(_ck())
    fresh = isinstance(hit, dict) and time.time() - float(hit.get("_ts", 0)) < 20 * 60
    if kick and not fresh and (_TASK is None or _TASK.done()):
        try:
            _TASK = asyncio.get_running_loop().create_task(refresh())
        except RuntimeError:
            pass
    return hit if isinstance(hit, dict) else None


# ---------------------------------------------------------------- v7
def _consecutive(hours: list[datetime], n: int) -> bool:
    if len(hours) < n:
        return False
    hs = hours[-n:]
    return all((hs[k] - hs[k - 1]) == timedelta(hours=1) for k in range(1, n))


def _record_run(run_id: str, t_issue: datetime, status: str, groups: dict[str, bool] | None, nwp_runs: dict[str, Any] | None) -> None:
    try:
        from app.store import pn_runs

        pn_runs.upsert_run({
            "run_id": run_id, "version": "v7", "t_issue_ms": int(t_issue.replace(tzinfo=UTC).timestamp() * 1000),
            "run_at_ms": int(time.time() * 1000), "status": status, "groups": groups or {}, "nwp": nwp_runs or {},
        })
    except Exception:  # noqa: BLE001
        pass


def _verify_pending(hours: list[datetime], rain_q: dict[datetime, np.ndarray]) -> None:
    """Score cached forecasts (0.5° event masks) against IMERG hours that have arrived since."""
    from app.science.pn import v7
    from app.store import pn_runs

    for key, fc in list((cache.get("pn7:fc:index") or {}).items()):
        f = cache.get(key)
        if not isinstance(f, dict):
            continue
        done = pn_runs.verified_leads(f["run_id"])
        for L in range(1, 13):
            vh = f["t_issue"] + timedelta(hours=L - 1)
            if L in done or vh not in rain_q:
                continue
            ob = v7.pool(rain_q[vh] > THR_Q)
            ev = np.unpackbits(f["ev"][L - 1])[: ob.size].reshape(ob.shape).astype(bool)
            pe = np.unpackbits(f["pers"])[: ob.size].reshape(ob.shape).astype(bool)
            sc = _score(ev, ob)
            ps = _score(pe, ob)
            pn_runs.add_verification(f["run_id"], L, {**pn_runs.scores(sc["hits"], sc["false_alarms"], sc["misses"]), "pc": ps["csi"]})


THR_Q = float(np.log1p(1.0))


def _build_v7(obs: dict[str, Any], nwp: dict[str, Any] | None, nwp_val: dict[str, Any] | None, pnc: dict[str, Any] | None = None) -> dict[str, Any]:
    """v7 pack + (when enabled) the separate PN-Correct layer under "pn_correct". The v7 field is never altered."""
    from app.science.pn import hooks

    layer = None
    if pnc is not None and obs.get("hours"):
        T = (obs["hours"][-1] + timedelta(hours=1)).replace(tzinfo=None)
        layer = hooks.correct({"t_issue": T, "pnc": pnc})
    pack = _build_v7_core(obs, nwp, nwp_val, layer)
    if layer is not None:
        pack["pn_correct"] = layer
    return pack


def _build_v7_core(obs: dict[str, Any], nwp: dict[str, Any] | None, nwp_val: dict[str, Any] | None, corrected: dict[str, Any] | None) -> dict[str, Any]:
    from app.science.pn import hooks, params, v7

    now = datetime.now(UTC)
    hours, rain = obs["hours"], obs["rain"]
    cfgp = params()["pn_nowcast_v7"]
    base: dict[str, Any] = {
        "model": "PRITHVI-Nowcast v7 (R2 + PN-Blend, ONNX CPU)",
        "version": "v7",
        "input": "IMERG Early hourly (last 6 h, 0.1°) + GFS/IFS rain and environment (latency-respecting runs); India domain",
        "imerg_note": "Trained on IMERG Late; live input is IMERG Early (Late arrives too late for a nowcast).",
        "nwp_latency_rule": "GFS run ≤ T−6 h, IFS run ≤ T−8 h (T = first forecast hour)",
        "event": "rain ≥ 1 mm/h", "verification_scale_deg": 0.5,
        "test_csi": {str(L): cfgp["test_by_lead_h"][str(L)]["final"]["csi"] for L in (1, 3, 6, 12)},
        "generated": now.isoformat(), "errors": (obs.get("errors") or []) + ((nwp or {}).get("errors") or []),
    }
    if not hours:
        return {**base, "ok": False, "status": "insufficient_imerg", "n_hours": 0}
    last = hours[-1]
    if not _consecutive(hours, 6):
        # IMERG gap: v7 needs 6 consecutive hours → persistence of the newest hour (if not stale)
        age0 = (now - (last + timedelta(hours=1))).total_seconds() / 3600
        if age0 > stale_h():
            return {**base, "ok": False, "status": "insufficient_imerg", "n_hours": len(hours)}
        _record_run(f"v7-{last + timedelta(hours=1):%Y%m%d%H}", (last + timedelta(hours=1)).replace(tzinfo=None), "persistence_fallback", None, None)
        return {
            **base, "ok": True, "status": "persistence_fallback", "last_obs_hour": last.isoformat(), "obs_age_h": round(age0, 2),
            "note": "IMERG has a gap (fewer than 6 consecutive hours); v7 not run. Persistence of the last observed hour.",
            "persistence_cells": _cells(rain[-1] >= 1.0, np.minimum(rain[-1] / 10.0, 1.0)),
        }
    t_issue = last + timedelta(hours=1)
    run_id = f"v7-{t_issue:%Y%m%d%H}"
    age_h = (now - t_issue).total_seconds() / 3600
    rq = {h: v7.quantise(r[None])[0] for h, r in zip(hours, rain)}
    try:
        _verify_pending(hours, rq)
    except Exception:  # noqa: BLE001
        pass
    base.update({"last_obs_hour": last.isoformat(), "obs_age_h": round(age_h, 2), "run_id": run_id})
    if age_h > stale_h():
        pers = rain[-1]
        _record_run(run_id, t_issue.replace(tzinfo=None), "persistence_fallback", None, None)
        return {
            **base, "ok": True, "status": "persistence_fallback",
            "note": f"Newest IMERG hour is {age_h:.1f} h old (> PN_STALE_OBS_H={stale_h():g}); v7 not run. Persistence of the last observed hour.",
            "persistence_cells": _cells(pers >= 1.0, np.minimum(pers / 10.0, 1.0)),
        }
    t0 = time.time()
    r = v7.run(np.stack(rain[-6:]), t_issue, nwp)
    run_ms = round((time.time() - t0) * 1000)
    if not r.get("ok"):
        return {**base, "ok": False, "status": r.get("status")}
    ctx = {"t_issue": t_issue, "rain_q": np.stack([rq[h] for h in hours[-6:]]), "nwp": nwp, "out": r}
    judged = hooks.judge(ctx)  # PN-Judge failed its pre-registered test → stays off (returns None)
    g = r["groups"]
    ops = cfgp["ops_blend"]
    leads = []
    for L in range(12):
        vs = last + timedelta(hours=L + 1)
        lead_now = round((vs - now).total_seconds() / 60)
        sk = cfgp["test_by_lead_h"][str(L + 1)]["final"]
        row = {
            "lead_h": L + 1, "valid_start": vs.isoformat(), "lead_from_now_min": lead_now, "past": lead_now < 0,
            "cut_0p1": ops["0.1"]["csi"][L], "cut_0p5": ops["0.5"]["csi"][L],
            "n_rain_px": int(r["rain_event"][L].sum()), "n_rain_cells_0p5": int(r["rain_event_0p5"][L].sum()),
            "max_mm_h": round(float(r["mm_h"][L].max()), 1), "test_csi": sk["csi"], "skill_sr": round(1 - sk["far"], 3),
            "rain_cells": _cells(r["rain_event"][L], r["p_rain"][L], 60) if lead_now >= -60 else [],
            "nowcast_weight": hooks.handover_weight(L + 1, bool(corrected and corrected.get("ok"))),
        }
        if judged and (L + 1) in judged:
            row["judge"] = judged[L + 1]
        leads.append(row)
    # cache the 0.5° event masks so later refreshes can verify each lead once IMERG arrives
    try:
        key = f"pn7:fc:{run_id}"
        cache.set(key, {"run_id": run_id, "t_issue": t_issue, "ev": [np.packbits(e.ravel()) for e in r["rain_event_0p5"]],
                        "pers": np.packbits(v7.pool(rq[last] > THR_Q).ravel())}, 20 * 3600)
        idx = dict(cache.get("pn7:fc:index") or {}); idx[key] = t_issue.isoformat()
        cutoff = t_issue - timedelta(hours=20)
        idx = {k: v for k, v in idx.items() if datetime.fromisoformat(v) >= cutoff}
        cache.set("pn7:fc:index", idx, 24 * 3600)
    except Exception:  # noqa: BLE001
        pass
    _record_run(run_id, t_issue.replace(tzinfo=None), "model", g, r["nwp_runs"])
    # live validation: rerun with the window ending 3 h earlier, score leads 1..3 (0.5°)
    val = None
    if _consecutive(hours, 9):
        rv = v7.run(np.stack(rain[-9:-3]), hours[-4] + timedelta(hours=1), nwp_val)
        if rv.get("ok"):
            val = {"input_end_hour": hours[-4].isoformat(), "groups": rv["groups"], "by_lead": []}
            for L in range(3):
                ob = v7.pool(rq[hours[-3 + L]] > THR_Q)
                val["by_lead"].append({
                    "lead_h": L + 1, "valid_start": hours[-3 + L].isoformat(),
                    "rain_ge1_0p5": _score(rv["rain_event_0p5"][L], ob),
                    "persistence_rain_ge1_0p5": _score(v7.pool(rq[hours[-4]] > THR_Q), ob),
                })
    try:
        from app.store import pn_runs

        pn_runs.track(30, "v7")
    except Exception:  # noqa: BLE001
        pass
    return {
        **base, "ok": True, "status": "ok", "run_ms": run_ms,
        "input_hours": [h.isoformat() for h in hours[-6:]],
        "groups_live": [k for k, v in g.items() if v], "groups_masked": [k for k, v in g.items() if not v],
        "nwp_runs": r["nwp_runs"], "nwp_age_h": r["nwp_age_h"],
        "hooks": hooks.status(), "leads": leads, "validation": val,
    }

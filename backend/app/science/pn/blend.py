"""PN-Blend rain post-processor (research `run_rain_ts`, fixed per-lead weights).

blend_L = w_E(L)·extrapolation_L + w_G(L)·GFS_L + w_I(L)·IFS_L

* extrapolation member = the app's own observation-anchored nowcast for the pin
  (`science.nowcast.hours[*].mm`). If its observations are stale (> PN_STALE_OBS_H, default
  3 h) it is replaced by **persistence** of the last observed rate, flagged.
* GFS / IFS members = Open-Meteo hourly precipitation for `gfs_global` / `ecmwf_ifs025`
  (already fetched by the snapshot — no extra calls). Open-Meteo serves the newest run that
  has been published, which already satisfies the research latency rule (GFS ≥ 6 h,
  IFS ≥ 8 h after init); a member is dropped if its valid times do not cover the lead.
* Missing members → weights renormalised over the members that exist.
* Event flag (rain ≥ 1 mm/h) uses the research FAR-capped per-lead cut-off applied to a
  member-agreement probability.
"""

from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from typing import Any

from app.science.pn import params


def _parse(t: str, naive_offset_s: int = 0) -> datetime | None:
    try:
        d = datetime.fromisoformat(str(t).replace("Z", "+00:00"))
    except ValueError:
        return None
    if d.tzinfo:
        return d
    return d.replace(tzinfo=timezone.utc) - timedelta(seconds=naive_offset_s)


IST_OFFSET_S = 19800  # every Open-Meteo call in this app uses timezone=Asia/Kolkata


def _hourly(raw: dict[str, Any] | None, utc_offset_s: int = IST_OFFSET_S) -> dict[datetime, float]:
    hr = (raw or {}).get("hourly") or {}
    ts = hr.get("time") or []
    pr = hr.get("precipitation") or []
    off = int((raw or {}).get("utc_offset_seconds", utc_offset_s))
    out: dict[datetime, float] = {}
    for t, v in zip(ts, pr):
        if v is None:
            continue
        d = _parse(t, off)
        if d is None:
            continue
        out[d.replace(minute=0, second=0, microsecond=0)] = float(v)
    return out


def _member(models: dict[str, Any], *ids: str) -> dict[datetime, float]:
    for sid in ids:
        raw = models.get(sid)
        if isinstance(raw, dict) and raw.get("hourly"):
            got = _hourly(raw)
            if got:
                return got
    return {}


def blend(
    nowcast: dict[str, Any],
    models: dict[str, Any],
    *,
    now: datetime | None = None,
    max_lead_h: int = 12,
) -> dict[str, Any]:
    p = params()
    W = p["pn_blend_rain"]["weights_by_lead_h"]
    cuts = p["pn_net_v4"]["calibration"]["rain"]["cut"]
    now = (now or datetime.now(timezone.utc)).replace(minute=0, second=0, microsecond=0)
    hours = list((nowcast or {}).get("hours") or [])
    observed = list((nowcast or {}).get("observed") or [])
    stale_h = float(os.environ.get("PN_STALE_OBS_H") or 3)
    last_obs_t = None
    last_obs_mm = None
    for o in observed:
        d = _parse(o.get("t") or "", IST_OFFSET_S)
        if d is not None and (last_obs_t is None or d > last_obs_t):
            last_obs_t, last_obs_mm = d, o.get("mm")
    obs_age_h = (now - last_obs_t).total_seconds() / 3600.0 if last_obs_t else None
    stale = obs_age_h is None or obs_age_h > stale_h
    gfs = _member(models, "gfs")
    ifs = _member(models, "ifs025")
    ext_by_lead: dict[int, float] = {}
    for h in hours:
        try:
            ext_by_lead[int(h.get("lead_h"))] = float(h.get("mm") or 0.0)
        except (TypeError, ValueError):
            continue
    rows = []
    for L in range(1, max_lead_h + 1):
        w = W.get(str(L)) or W[str(max(int(k) for k in W))]
        t = now + timedelta(hours=L)
        mem: dict[str, float] = {}
        if stale:
            if last_obs_mm is not None and L <= 2:
                mem["extrap"] = float(last_obs_mm)  # persistence fallback, short leads only
        elif L in ext_by_lead:
            mem["extrap"] = ext_by_lead[L]
        if t in gfs:
            mem["gfs"] = gfs[t]
        if t in ifs:
            mem["ifs"] = ifs[t]
        if not mem:
            continue
        ws = {k: float(w[k]) for k in mem}
        tot = sum(ws.values()) or 1.0
        val = sum(mem[k] * ws[k] for k in mem) / tot
        p_wet = sum(ws[k] for k in mem if mem[k] >= 1.0) / tot
        cut = float(cuts[min(L, len(cuts)) - 1])
        rows.append(
            {
                "t": t.isoformat().replace("+00:00", "Z"),
                "lead_h": L,
                "mm": round(val, 2),
                "p_ge_1mm": round(p_wet, 2),
                "event": bool(val >= 1.0 and p_wet >= max(cut, 0.5)),
                "members": {k: round(v, 2) for k, v in mem.items()},
                "weights": {k: round(ws[k] / tot, 2) for k in ws},
            }
        )
    return {
        "method": "PN-Blend (research fixed per-lead weights: extrapolation/GFS/IFS)",
        "hours": rows,
        "extrap_source": "persistence (observations stale)" if stale else "app nowcast",
        "obs_age_h": round(obs_age_h, 2) if obs_age_h is not None else None,
        "members_available": {"extrap": bool(ext_by_lead) and not stale, "gfs": bool(gfs), "ifs": bool(ifs)},
        "latency_rule": p["pn_blend_rain"]["latency_rule"],
        "note": "Post-processing of real model/observation series; not a gauge.",
    }

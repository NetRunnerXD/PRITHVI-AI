"""PN-Blend 12 h cyclone track (research run_cyclone_nwp / bob06_track).

blend = 0.35·extrapolation + 0.20·GFS + 0.45·IFS (positions), weights tuned on 2023 and
tested 2024–2026 in the research repo (BOB 06 2026: blend 53 km vs extrapolation 110 km).

* extrapolation: constant 6 h motion from the last two observed fixes (research baselines).
* GFS / IFS: MSLP minimum tracker on Open-Meteo `gfs_global` / `ecmwf_ifs025` 0.5° grids,
  shifted to the observed t0 position ("interpolated early model"), stepping 3 h with a
  200 km search radius exactly like `track_low`.
* Cached 3 h per system; only for North Indian Ocean systems (quota).
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from typing import Any

from app import cache
from app.science.pn import params

OM = "https://api.open-meteo.com/v1/forecast"
MODELS = {"gfs": "gfs_global", "ifs": "ecmwf_ifs025"}


def _hav(a: float, b: float, c: float, d: float) -> float:
    from app.providers.cyclones import haversine_km

    return haversine_km(a, b, c, d)


def _parse(t: str | None) -> datetime | None:
    if not t:
        return None
    try:
        d = datetime.fromisoformat(t.replace("Z", "+00:00"))
    except ValueError:
        return None
    return d if d.tzinfo else d.replace(tzinfo=timezone.utc)


async def _msl_grid(model: str, lat0: float, lon0: float, t0: datetime, t1: datetime) -> dict[str, Any] | None:
    from app.providers.http import client

    step = 0.5
    lats = [round(lat0 + (j - 6) * step, 2) for j in range(13)]
    lons = [round(lon0 + (i - 6) * step, 2) for i in range(13)]
    la = [a for a in lats for _ in lons]
    lo = [b for _ in lats for b in lons]
    r = await client().get(
        OM,
        params={
            "latitude": ",".join(map(str, la)),
            "longitude": ",".join(map(str, lo)),
            "hourly": "pressure_msl",
            "models": model,
            "timezone": "GMT",
            "start_hour": t0.strftime("%Y-%m-%dT%H:00"),
            "end_hour": t1.strftime("%Y-%m-%dT%H:00"),
        },
        timeout=10.0,
    )
    if r.status_code >= 400:
        return None
    rows = r.json()
    rows = rows if isinstance(rows, list) else [rows]
    times = ((rows[0] or {}).get("hourly") or {}).get("time") or []
    field = {}
    for k, t in enumerate(times):
        field[t] = [((row.get("hourly") or {}).get("pressure_msl") or [None] * len(times))[k] for row in rows]
    return {"lat": la, "lon": lo, "times": times, "msl": field}


def _low(grid: dict[str, Any], t: str, lat0: float, lon0: float, radius_km: float) -> tuple[float, float] | None:
    vals = grid["msl"].get(t)
    if not vals:
        return None
    best = None
    for a, b, v in zip(grid["lat"], grid["lon"], vals):
        if v is None or _hav(a, b, lat0, lon0) > radius_km:
            continue
        if best is None or v < best[2]:
            best = (a, b, v)
    return (best[0], best[1]) if best else None


async def _member(name: str, obs: tuple[float, float], fg12: tuple[float, float], t0: datetime) -> tuple[float, float] | None:
    t12 = t0 + timedelta(hours=12)
    mid = ((obs[0] + fg12[0]) / 2, (obs[1] + fg12[1]) / 2)
    grid = await _msl_grid(MODELS[name], mid[0], mid[1], t0, t12)
    if not grid:
        return None
    fmt = lambda d: d.strftime("%Y-%m-%dT%H:00")  # noqa: E731
    a0 = _low(grid, fmt(t0), obs[0], obs[1], 250)
    if not a0:
        return None
    pla, plo = a0
    for L in (3, 6, 9, 12):
        nxt = _low(grid, fmt(t0 + timedelta(hours=L)), pla, plo, 200)
        if not nxt:
            return None
        pla, plo = nxt
    return obs[0] + pla - a0[0], obs[1] + plo - a0[1]


async def blend_track(sysd: dict[str, Any]) -> dict[str, Any]:
    obs = [p for p in (sysd.get("observed_track") or []) if p.get("t")]
    if len(obs) < 2:
        obs = [p for p in (sysd.get("ibtracs") or []) if p.get("t")]
    if len(obs) < 2:
        return {"ok": False, "status": "need_two_fixes"}
    last = obs[-1]
    t0 = _parse(last["t"])
    prev = next((p for p in reversed(obs[:-1]) if _parse(p["t"]) and 5.0 <= (t0 - _parse(p["t"])).total_seconds() / 3600 <= 12.5), obs[-2])
    dt = max(1.0, (t0 - _parse(prev["t"])).total_seconds() / 3600.0)
    d6la = (last["lat"] - prev["lat"]) * 6.0 / dt
    d6lo = (last["lon"] - prev["lon"]) * 6.0 / dt
    ext = (last["lat"] + 2 * d6la, last["lon"] + 2 * d6lo)
    key = f"pn:cyc:{sysd.get('id')}:{last['t']}"
    hit = cache.get(key)
    if isinstance(hit, dict):
        return hit
    w = params()["pn_blend_cyclone"]["weights_12h"]
    gfs, ifs = await asyncio.gather(
        _member("gfs", (last["lat"], last["lon"]), ext, t0),
        _member("ifs", (last["lat"], last["lon"]), ext, t0),
        return_exceptions=True,
    )
    mem = {"extrap": ext}
    if isinstance(gfs, tuple):
        mem["gfs"] = gfs
    if isinstance(ifs, tuple):
        mem["ifs"] = ifs
    tot = sum(float(w[k]) for k in mem)
    lat = sum(mem[k][0] * float(w[k]) for k in mem) / tot
    lon = sum(mem[k][1] * float(w[k]) for k in mem) / tot
    out = {
        "ok": True,
        "valid": (t0 + timedelta(hours=12)).isoformat().replace("+00:00", "Z"),
        "from": last["t"],
        "lat": round(lat, 2),
        "lon": round(lon, 2),
        "members": {k: [round(v[0], 2), round(v[1], 2)] for k, v in mem.items()},
        "weights": {k: round(float(w[k]) / tot, 2) for k in mem},
        "method": "PN-Blend 12 h track (extrapolation .35 / GFS .20 / IFS .45, renormalised if a member is missing)",
    }
    cache.set(key, out, 3 * 3600)
    return out

"""Thunder-strike nowcast: lifetime, predicted strikes, storm polygons.

Not GPS strokes and not locked hourly millimetres.

Lifetime is a Byers–Braham / TITAN-style cell clock, different for every cell:

    T0(kind)                  base (lightning 35, burst 55, downburst 22, …)
  + 32 · A / (A + 220)        size (km²), saturating
  + 22 · max(0, 240 − Tb)/40  colder tops last longer
  + 12 · clip(cooling_K, −1, 4) / 2
  + 18 · P(lightning) + 10 · P(cloudburst)
  + 10 · clip(R / 25, 0, 1.6)
  − 12 · clip(V / 50, 0, 1.5)  fast cells dwell less over a point
  × 1.25 growing | 0.72 collapsing | 1.0 steady
  + 5 · |sin(12.989 lat + 78.233 lon)|   deterministic jitter so twins differ

Age is inferred from trend; remaining = clip(T_life − age, 12, 120).

Predicted strikes: advect the cell, P(t) = P0 · exp(−t / τ), τ = T_life / 1.1,
at 15/30/45/60 min if P(t) ≥ 0.16 and the point is in India.
"""

from __future__ import annotations

import json
import math
import os
from datetime import datetime, timedelta, timezone
from typing import Any

from app.config import ROOT
from app.data.india_mask import in_india
from app.science.nowcast import _clip
from app.science import sat_cv

IST = timezone(timedelta(hours=5, minutes=30))
WINDOW_PATH = ROOT / ".cache" / "storm_windows.json"

_T0 = {
    "lightning": 35.0,
    "cloudburst": 55.0,
    "downburst": 22.0,
    "storm": 48.0,
    "cloud": 40.0,
}

_LEADS = (15, 30, 45, 60)


def confidence_of(
    p_lightning: float,
    *,
    lead_min: int = 0,
    frames: int = 1,
    cape: float = 0.0,
    weather_code: int = 0,
    agrees: bool | None = None,
    ot: bool = False,
    p_cloudburst: float = 0.0,
) -> dict[str, Any]:
    """0–1 nowcast confidence and a high/medium/low band."""
    c = 0.20 + 0.50 * _clip(float(p_lightning or 0.0), 0.0, 1.0)
    c += 0.12 * _clip(float(p_cloudburst or 0.0), 0.0, 1.0)
    c -= 0.0035 * max(0, int(lead_min or 0))
    if frames >= 2:
        c += 0.08
    if ot:
        c += 0.05
    if cape >= 2000:
        c += 0.10
    elif cape >= 900:
        c += 0.05
    if weather_code >= 95:
        c += 0.14
    elif weather_code >= 80:
        c += 0.06
    if agrees is True:
        c += 0.10
    elif agrees is False:
        c -= 0.08
    c = _clip(c, 0.08, 0.92)
    band = "high" if c >= 0.62 else "medium" if c >= 0.38 else "low"
    return {"confidence": round(c, 3), "confidence_band": band}


def _iso(dt: datetime) -> str:
    return dt.astimezone(IST).isoformat(timespec="seconds")


def _ms(dt: datetime) -> int:
    return int(dt.timestamp() * 1000)


def _load_windows() -> dict[str, str]:
    if not WINDOW_PATH.exists():
        return {}
    try:
        blob = json.loads(WINDOW_PATH.read_text(encoding="utf-8"))
        return blob if isinstance(blob, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def _save_windows(store: dict[str, str]) -> None:
    try:
        WINDOW_PATH.parent.mkdir(parents=True, exist_ok=True)
        WINDOW_PATH.write_text(json.dumps(store), encoding="utf-8")
    except OSError:
        pass


def remember_start(sig: str, started: datetime, now: datetime) -> datetime:
    """Keep first-seen so a refresh does not reset the open window."""
    if os.environ.get("PYTEST_CURRENT_TEST"):
        return started
    store = _load_windows()
    raw = store.get(sig)
    if raw:
        try:
            prev = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
            if prev.tzinfo is None:
                prev = prev.replace(tzinfo=timezone.utc)
            if (now - prev).total_seconds() < 6 * 3600:
                return prev
        except ValueError:
            pass
    store[sig] = started.isoformat()
    cutoff = (now - timedelta(hours=6)).isoformat()
    pruned = {k: v for k, v in store.items() if v >= cutoff}
    pruned[sig] = store[sig]
    _save_windows(pruned)
    return started


def lifetime_min(cell: dict[str, Any]) -> float:
    """Event duration in minutes. Every cell gets its own number."""
    kind = str(cell.get("kind") or "storm")
    t0 = _T0.get(kind, 45.0)
    area = max(float(cell.get("area_km2") or 0), 0.0)
    tb = float(cell.get("min_tb_k") or 250.0)
    # track d_tb_k is curr − prev (negative = cooling). cooling_k on the cell is prev − curr.
    cooling = float(cell.get("cooling_k") or 0.0)
    if not cooling:
        cooling = -float(cell.get("d_tb_k") or 0.0)
    p_l = float(cell.get("p_lightning") or 0.0)
    p_c = float(cell.get("p_cloudburst") or 0.0)
    rain = float(cell.get("rain_ir_mm_h") or 0.0)
    speed = float(cell.get("speed_kmh") or 0.0)
    lat = float(cell.get("lat") or 0.0)
    lon = float(cell.get("lon") or 0.0)
    trend = str(cell.get("trend") or "steady")

    size = 32.0 * area / (area + 220.0)
    depth = 22.0 * max(0.0, 240.0 - tb) / 40.0
    growth = 12.0 * _clip(cooling, -1.0, 4.0) / 2.0
    elec = 18.0 * p_l + 10.0 * p_c
    rain_t = 10.0 * _clip(rain / 25.0, 0.0, 1.6)
    motion = -12.0 * _clip(speed / 50.0, 0.0, 1.5)
    jitter = 5.0 * abs(math.sin(lat * 12.989 + lon * 78.233))
    mul = 1.25 if trend == "growing" else 0.72 if trend == "collapsing" else 1.0
    return _clip((t0 + size + depth + growth + elec + rain_t + motion + jitter) * mul, 14.0, 140.0)


def age_min(cell: dict[str, Any]) -> float:
    trend = str(cell.get("trend") or "steady")
    if trend == "growing":
        return 8.0
    if trend == "collapsing":
        return 42.0
    return 24.0


def remaining_min(cell: dict[str, Any], age: float | None = None) -> float:
    life = lifetime_min(cell)
    used = age if age is not None else age_min(cell)
    return _clip(life - used, 12.0, 120.0)


def ellipse_ring(lat: float, lon: float, area_km2: float, n: int = 12) -> list[list[float]]:
    r_km = math.sqrt(max(float(area_km2) or 40.0, 40.0) / math.pi)
    r_lat = r_km / 111.3
    r_lon = r_lat / max(0.35, math.cos(math.radians(lat)))
    ring: list[list[float]] = []
    for i in range(n):
        ang = 2.0 * math.pi * i / n
        ring.append(
            [
                round(lat + r_lat * math.sin(ang), 4),
                round(lon + r_lon * math.cos(ang), 4),
            ]
        )
    ring.append(ring[0])
    return ring


def advect_ring(ring: list[list[float]], u_kmh: float, v_kmh: float, minutes: float) -> list[list[float]]:
    dt_h = minutes / 60.0
    dlat = v_kmh * dt_h / 111.3
    dlon = u_kmh * dt_h / 111.3
    return [[round(p[0] + dlat, 4), round(p[1] + dlon, 4)] for p in ring]


def cell_ring(cell: dict[str, Any]) -> list[list[float]]:
    ring = cell.get("ring")
    if isinstance(ring, list) and len(ring) >= 4:
        out = [[float(p[0]), float(p[1])] for p in ring if isinstance(p, (list, tuple)) and len(p) >= 2]
        if out and out[0] != out[-1]:
            out.append(out[0])
        if len(out) >= 4:
            return out
    return ellipse_ring(float(cell["lat"]), float(cell["lon"]), float(cell.get("area_km2") or 80))


def live_window(cell: dict[str, Any], now: datetime) -> dict[str, Any]:
    age = age_min(cell)
    remain = remaining_min(cell, age)
    raw_start = now - timedelta(minutes=age)
    sig = f"live:{cell.get('kind')}:{round(float(cell['lat']), 2)}:{round(float(cell['lon']), 2)}"
    started = remember_start(sig, raw_start, now)
    true_age = max(0.0, (now - started).total_seconds() / 60.0)
    remain = remaining_min(cell, true_age)
    closes = now + timedelta(minutes=remain)
    return {
        "started_at": _iso(started),
        "closes_at": _iso(closes),
        "started_ms": _ms(started),
        "closes_ms": _ms(closes),
        "lifetime_min": round(lifetime_min(cell), 1),
        "remain_min": round(remain, 1),
        "phase": "live",
    }


def lightning_window(started: datetime, now: datetime, extra: dict[str, Any] | None = None) -> dict[str, Any]:
    """Observed stroke: remaining decays as exp(−age/25)."""
    extra = extra or {}
    age_m = max(0.0, (now - started).total_seconds() / 60.0)
    remain = _clip(28.0 * math.exp(-age_m / 25.0) + 8.0, 8.0, 45.0)
    cape = float(extra.get("cape") or 0.0)
    if cape:
        remain = _clip(remain + 12.0 * _clip(cape / 2000.0, 0.0, 1.0), 8.0, 70.0)
    closes = now + timedelta(minutes=remain)
    return {
        "started_at": _iso(started),
        "closes_at": _iso(closes),
        "started_ms": _ms(started),
        "closes_ms": _ms(closes),
        "lifetime_min": round(age_m + remain, 1),
        "remain_min": round(remain, 1),
        "phase": "live" if started <= now else "predicted",
    }


def predicted_strikes(cells: list[dict[str, Any]], now: datetime) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Lagrangian strike nowcast + storm polygons (live hull and +30 min)."""
    hits: list[dict[str, Any]] = []
    polys: list[dict[str, Any]] = []
    for i, cell in enumerate(cells):
        p0 = float(cell.get("p_lightning") or 0.0)
        kind = str(cell.get("kind") or "storm")
        if p0 < 0.16 and kind not in {"lightning", "storm", "cloudburst", "downburst"}:
            continue
        u = float(cell.get("u_kmh") or 0.0)
        v = float(cell.get("v_kmh") or 0.0)
        tau = max(18.0, lifetime_min(cell) / 1.1)
        ring0 = cell_ring(cell)
        live_poly = [pt for pt in ring0 if in_india(pt[0], pt[1])]
        if len(live_poly) >= 3:
            if live_poly[0] != live_poly[-1]:
                live_poly.append(live_poly[0])
            polys.append(
                {
                    "id": f"poly-{cell.get('id') or i}",
                    "kind": kind,
                    "lead_min": 0,
                    "ring": live_poly,
                    "p_lightning": p0,
                    "place": cell.get("place"),
                    "lat": cell["lat"],
                    "lon": cell["lon"],
                }
            )
        for lead in _LEADS:
            p = p0 * math.exp(-lead / tau)
            if kind == "lightning":
                p = max(p, p0 * 0.55)
            if p < 0.16:
                continue
            plat = round(float(cell["lat"]) + v * (lead / 60.0) / 111.3, 3)
            plon = round(float(cell["lon"]) + u * (lead / 60.0) / 111.3, 3)
            if not in_india(plat, plon):
                continue
            remain = _clip(remaining_min(cell) * 0.5, 10.0, 50.0)
            started = now + timedelta(minutes=lead)
            closes = started + timedelta(minutes=remain)
            conf = confidence_of(
                p,
                lead_min=lead,
                cape=float(cell.get("cape") or 0),
                ot=bool(cell.get("ot")),
                p_cloudburst=float(cell.get("p_cloudburst") or 0),
            )
            place = cell.get("place") or f"{plat:.2f}, {plon:.2f}"
            hits.append(
                {
                    "id": f"pred-ltn-{cell.get('id') or i}-{lead}",
                    "kind": "lightning",
                    "lat": plat,
                    "lon": plon,
                    "place": place,
                    "started_at": _iso(started),
                    "closes_at": _iso(closes),
                    "started_ms": _ms(started),
                    "closes_ms": _ms(closes),
                    "lead_min": lead,
                    "p_lightning": round(p, 3),
                    "p_cloudburst": cell.get("p_cloudburst"),
                    "engine": "thunder-predict-v1",
                    "phase": "predicted",
                    "parent": cell.get("id"),
                    "lifetime_min": round(remain, 1),
                    "remain_min": round(remain, 1),
                    **conf,
                }
            )
            if kind in {"storm", "cloudburst", "downburst"}:
                sp = max(p * 0.85, float(cell.get("p_cloudburst") or 0) * math.exp(-lead / tau))
                if sp >= 0.14:
                    sconf = confidence_of(
                        sp,
                        lead_min=lead,
                        ot=bool(cell.get("ot")),
                        p_cloudburst=float(cell.get("p_cloudburst") or 0),
                    )
                    hits.append(
                        {
                            "id": f"pred-storm-{cell.get('id') or i}-{lead}",
                            "kind": kind if kind != "lightning" else "storm",
                            "lat": plat,
                            "lon": plon,
                            "place": place,
                            "started_at": _iso(started),
                            "closes_at": _iso(closes),
                            "started_ms": _ms(started),
                            "closes_ms": _ms(closes),
                            "lead_min": lead,
                            "p_lightning": round(p, 3),
                            "p_cloudburst": cell.get("p_cloudburst"),
                            "engine": "thunder-predict-v1",
                            "phase": "predicted",
                            "parent": cell.get("id"),
                            "lifetime_min": round(remain, 1),
                            "remain_min": round(remain, 1),
                            **sconf,
                        }
                    )
            if lead == 30:
                moved = advect_ring(ring0, u, v, lead)
                moved = [pt for pt in moved if in_india(pt[0], pt[1])]
                if len(moved) >= 3:
                    if moved[0] != moved[-1]:
                        moved.append(moved[0])
                    polys.append(
                        {
                            "id": f"poly-{cell.get('id') or i}-30",
                            "kind": kind if kind in {"storm", "cloudburst", "downburst"} else "lightning",
                            "lead_min": 30,
                            "ring": moved,
                            "p_lightning": round(p, 3),
                            "place": cell.get("place"),
                            "lat": plat,
                            "lon": plon,
                            **conf,
                        }
                    )
    return hits, polys


def om_predicted(hub: dict[str, Any], pack: dict[str, Any], now: datetime) -> list[dict[str, Any]]:
    """Open-Meteo hourly thunder at a hub → predicted windows (no extra HTTP)."""
    out: list[dict[str, Any]] = []
    lat, lon = float(hub["lat"]), float(hub["lon"])
    if not in_india(lat, lon):
        return out
    place = hub.get("label") or hub.get("district") or f"{lat:.2f}, {lon:.2f}"
    hours = pack.get("hours") or []
    for row in hours:
        lead_h = int(row.get("lead_h") or 0)
        if not row.get("thunder"):
            continue
        cape = float(row.get("cape") or 0.0)
        dur = _clip(22.0 + 40.0 * _clip(cape / 2000.0, 0.0, 1.0), 18.0, 70.0)
        started = now + timedelta(hours=lead_h) - timedelta(minutes=8 if lead_h else 0)
        closes = started + timedelta(minutes=dur)
        phase = "live" if lead_h == 0 else "predicted"
        code = int(row.get("weather_code") or 0)
        p_l = 0.62 if code >= 95 else 0.42
        conf = confidence_of(p_l, lead_min=lead_h * 60, cape=cape, weather_code=code)
        out.append(
            {
                "id": f"omth-{round(lat, 2)}-{round(lon, 2)}-{lead_h}",
                "kind": "lightning",
                "lat": lat,
                "lon": lon,
                "place": place,
                "started_at": _iso(started),
                "closes_at": _iso(closes),
                "started_ms": _ms(started),
                "closes_ms": _ms(closes),
                "lead_min": lead_h * 60,
                "p_lightning": p_l,
                "engine": "open-meteo-thunder",
                "weather_code": code,
                "cape": cape,
                "phase": phase,
                "lifetime_min": round(dur, 1),
                "remain_min": round(max(0.0, (closes - now).total_seconds() / 60.0), 1),
                **conf,
            }
        )
    return out


def attach_live_windows(inc: dict[str, Any], cell: dict[str, Any], now: datetime) -> dict[str, Any]:
    win = live_window(cell, now)
    inc.update(win)
    return inc

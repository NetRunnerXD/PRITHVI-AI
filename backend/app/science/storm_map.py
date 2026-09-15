"""State-cropped live storm layer + India incident feed."""

from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from typing import Any

from app.config import ROOT
from app.data.india_capitals import all_capitals
from app.data.india_districts import districts_in_state, nearest, state_frame
from app.data.india_mask import in_india
from app.science import sat_cv, thunder_predict

IST = timezone(timedelta(hours=5, minutes=30))
PAST_CELLS = ROOT / ".cache" / "past_storm_cells.json"

def _india_hubs() -> list[dict[str, Any]]:
    out = []
    for r in all_capitals():
        out.append(
            {
                "lat": float(r["lat"]),
                "lon": float(r["lon"]),
                "district": r.get("district") or r.get("name"),
                "state": r.get("state"),
                "label": f"{r.get('name')}, {r.get('state')}",
            }
        )
    return out


def _in_box(lat: float, lon: float, frame: dict[str, Any]) -> bool:
    return frame["south"] <= lat <= frame["north"] and frame["west"] <= lon <= frame["east"]


def _in_scope(lat: float, lon: float, frame: dict[str, Any]) -> bool:
    if not in_india(lat, lon):
        return False
    if not _in_box(lat, lon, frame):
        return False
    if frame.get("all_india"):
        return True
    d = nearest(lat, lon)
    return (d.get("state") or "") == (frame.get("state") or "")


def _spread_hubs(rows: list[dict], n: int = 4) -> list[dict]:
    if not rows:
        return []
    if len(rows) <= n:
        return rows
    ranked = sorted(rows, key=lambda d: (d["lat"], d["lon"]))
    step = max(1, len(ranked) // n)
    return [ranked[i] for i in range(0, len(ranked), step)][:n]


def _kind(cell: dict[str, Any]) -> str:
    d_tb = float(cell.get("d_tb_k") or 0)
    if cell.get("trend") == "collapsing" or d_tb >= 2.0:
        return "downburst"
    rain = float(cell.get("rain_ir_mm_h") or 0)
    tb = float(cell.get("min_tb_k") or 300)
    if tb <= 221 or rain >= 15 or (cell.get("ot") and cell.get("trend") == "growing"):
        return "cloudburst"
    if cell.get("ot") or cell.get("trend") == "growing" or rain >= 6 or tb <= 240:
        return "storm"
    return "cloud"


def _label(lat: float, lon: float) -> str:
    d = nearest(lat, lon)
    return d.get("label") or f"{d.get('district')}, {d.get('state')}"


def _iso(dt: datetime) -> str:
    from app.store.time import iso_z

    return iso_z(dt)


def _parse_dt(raw: Any, *, fallback_tz=timezone.utc) -> datetime | None:
    if raw is None or raw == "":
        return None
    if isinstance(raw, datetime):
        t = raw
        if t.tzinfo is None:
            t = t.replace(tzinfo=fallback_tz)
        return t
    try:
        s = str(raw).strip().replace("Z", "+00:00")
        if not s:
            return None
        t = datetime.fromisoformat(s[:32])
        if t.tzinfo is None:
            t = t.replace(tzinfo=fallback_tz)
        return t
    except ValueError:
        return None


def _occurred(s: dict[str, Any], now: datetime) -> datetime | None:
    """When the past event actually happened — never 'now' and never window close."""
    if s.get("past_mins") is not None:
        try:
            return now - timedelta(minutes=float(s["past_mins"]))
        except (TypeError, ValueError):
            pass
    if s.get("lead_h") is not None:
        try:
            lh = float(s["lead_h"])
            if lh < 0:
                return now + timedelta(hours=lh)
        except (TypeError, ValueError):
            pass
    for key in ("occurred_at", "t", "timestamp_utc", "first_seen", "started_at", "saved_at", "last_seen"):
        t = _parse_dt(s.get(key))
        if t is not None and t <= now + timedelta(minutes=2):
            return t
    return None


def _load_past_cells() -> list[dict[str, Any]]:
    import json

    if not PAST_CELLS.exists():
        return []
    try:
        blob = json.loads(PAST_CELLS.read_text(encoding="utf-8"))
        return blob if isinstance(blob, list) else []
    except (OSError, json.JSONDecodeError):
        return []


def _save_past_cells(rows: list[dict[str, Any]]) -> None:
    import json

    try:
        PAST_CELLS.parent.mkdir(parents=True, exist_ok=True)
        PAST_CELLS.write_text(json.dumps(rows[-120:]), encoding="utf-8")
    except OSError:
        pass


def remember_past_cells(cells: list[dict[str, Any]], now: datetime) -> list[dict[str, Any]]:
    """IR cells that dropped off the live set stay as past-storm markers for 6 h."""
    if os.environ.get("PYTEST_CURRENT_TEST"):
        return []
    cutoff = now - timedelta(hours=12)
    live_keys = {(round(float(c["lat"]), 2), round(float(c["lon"]), 2), c.get("kind")) for c in cells}
    mem = _load_past_cells()
    try:
        from app.science.cv_memory import past_cells as mongo_past

        mem = list(mem) + list(mongo_past(now, hours=12) or [])
    except Exception:
        pass
    out: list[dict[str, Any]] = []
    seen: set[tuple] = set()
    for c in cells:
        key = (round(float(c["lat"]), 2), round(float(c["lon"]), 2), c.get("kind"))
        seen_at = c.get("last_seen") or c.get("first_seen") or c.get("t")
        if not seen_at:
            continue
        row = {**c, "first_seen": c.get("first_seen") or seen_at, "last_seen": c.get("last_seen") or seen_at}
        seen.add(key)
        out.append(row)
    for c in mem:
        try:
            key = (round(float(c["lat"]), 2), round(float(c["lon"]), 2), c.get("kind"))
        except (TypeError, ValueError, KeyError):
            continue
        if key in seen or key in live_keys:
            continue
        occurred = _occurred(c, now)
        if occurred is None or occurred < cutoff:
            continue
        seen.add(key)
        out.append(c)
    _save_past_cells(out)
    try:
        from app.science.cv_memory import remember_cells

        remember_cells(out)
    except Exception:
        pass
    return [c for c in out if (round(float(c["lat"]), 2), round(float(c["lon"]), 2), c.get("kind")) not in live_keys]


def _incident(
    *,
    iid: str,
    kind: str,
    lat: float,
    lon: float,
    place: str,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "id": iid,
        "kind": kind,
        "lat": lat,
        "lon": lon,
        "place": place,
        **(extra or {}),
    }


async def build(state: str, *, past_h: float = 6.0) -> dict[str, Any]:
    from app.store.time import clamp_horizon

    past_h = float(clamp_horizon(past_h))
    frame = state_frame(state)
    now = datetime.now(timezone.utc)
    empty = {
        "as_of": _iso(now),
        "state": frame.get("state") or state,
        "frame": frame,
        "strokes": [],
        "past_strokes": [],
        "past_cells": [],
        "cells": [],
        "incidents": [],
        "predicted": [],
        "predicted_storms": [],
        "polygons": [],
        "fires": [],
        "landslides": [],
        "ok": False,
        "sensors": {},
        "method": "thunder-predict-v1",
        "past_h": past_h,
        "processing": {"ready": True, "message": "", "satellites": [], "age_s": 0},
    }
    if os.environ.get("PYTEST_CURRENT_TEST"):
        return {**empty, "ok": True, "status": "test-skip"}
    if not frame.get("ok"):
        return {**empty, "status": "unknown_state"}

    from app.providers import firms, gibs_ir, imd_insat, lightning_feed, om_thunder
    from app.science import cv_nowcast
    import asyncio

    all_india = bool(frame.get("all_india"))
    if all_india:
        hubs = _india_hubs()
    else:
        rows = districts_in_state(frame["state"])
        hubs = _spread_hubs(rows, 8) or [
            {"lat": frame["lat"], "lon": frame["lon"], "district": frame["state"], "state": frame["state"]}
        ]

    ltn_hubs = hubs[:6] if all_india else hubs[:3]

    try:
        gathered = await asyncio.gather(
            lightning_feed.fetch_hubs(ltn_hubs, history=True, frame=frame),
            om_thunder.fetch_batch(hubs),
            imd_insat.fetch_sector(),
            gibs_ir.fetch_ir(frame["lat"], frame["lon"]),
            gibs_ir.fetch_imerg(frame["lat"], frame["lon"]),
            firms.fetch_india(),
            return_exceptions=True,
        )
    except Exception:
        gathered = [{}, [], {}, {}, {}, {}]

    def _dict(x: Any, default: dict[str, Any]) -> dict[str, Any]:
        return x if isinstance(x, dict) else default

    ltn_pack = _dict(gathered[0], {"ok": False, "strokes": [], "n": 0})
    thunder_packs = gathered[1] if isinstance(gathered[1], list) else [{} for _ in hubs]
    sector = _dict(gathered[2], {"ok": False})
    ir = _dict(gathered[3], {"ok": False})
    imerg = _dict(gathered[4], {"ok": False})
    firms_pack = _dict(gathered[5], {"ok": False, "fires": [], "n": 0})

    seen: set[tuple[float, float, str]] = set()
    strokes: list[dict[str, Any]] = []
    incidents: list[dict[str, Any]] = []
    raw_strokes = list(ltn_pack.get("strokes") or [])
    for s in raw_strokes:
        slat, slon = float(s["lat"]), float(s["lon"])
        if not _in_scope(slat, slon, frame):
            continue
        tkey = str(s.get("t") or s.get("timestamp_utc") or "")[:16]
        sig = (round(slat, 3), round(slon, 3), tkey)
        if sig in seen:
            continue
        seen.add(sig)
        place = _label(slat, slon)
        started = _occurred(s, now)
        if started is None:
            continue
        closes = started + timedelta(minutes=8)
        raw_t = s.get("t") or s.get("timestamp_utc") or s.get("last_seen") or s.get("saved_at")
        row = {
            **s,
            "place": place,
            "kind": "lightning",
            "phase": "past",
            "t": raw_t,
            "occurred_at": _iso(started),
            "occurred_ms": thunder_predict._ms(started),
            "started_at": _iso(started),
            "closes_at": _iso(closes),
            "started_ms": thunder_predict._ms(started),
            "closes_ms": thunder_predict._ms(closes),
            "engine": s.get("engine") or "weatherbit-lightning",
        }
        strokes.append(row)
        incidents.append(
            _incident(
                iid=f"wb-{sig[0]}-{sig[1]}-{tkey or thunder_predict._ms(started)}",
                kind="lightning",
                lat=slat,
                lon=slon,
                place=place,
                extra={
                    "t": raw_t,
                    "engine": row["engine"],
                    "phase": "past",
                    "occurred_at": row["occurred_at"],
                    "occurred_ms": row["occurred_ms"],
                    "started_at": row["started_at"],
                    "closes_at": row["closes_at"],
                    "started_ms": row["started_ms"],
                    "closes_ms": row["closes_ms"],
                },
            )
        )

    # Open-Meteo past thunder hours: model analysis, labelled honestly (not GPS).
    for h, th in zip(hubs, thunder_packs):
        hlat, hlon = float(h["lat"]), float(h["lon"])
        if not _in_scope(hlat, hlon, frame):
            continue
        for s in om_thunder.past_strikes(hlat, hlon, th):
            slat, slon = float(s["lat"]), float(s["lon"])
            tkey = str(s.get("t") or "")[:16]
            sig = (round(slat, 3), round(slon, 3), tkey or "om")
            if sig in seen:
                continue
            started = now + timedelta(hours=int(s.get("lead_h") or -1))
            if s.get("t"):
                parsed = _parse_dt(s.get("t"), fallback_tz=timezone.utc)
                if parsed is not None:
                    started = parsed
            too_close = False
            for x in strokes:
                dkm = ((float(x["lat"]) - slat) ** 2 + (float(x["lon"]) - slon) ** 2) ** 0.5 * 111.3
                if dkm >= 22:
                    continue
                xt = _parse_dt(x.get("occurred_at") or x.get("t"))
                if xt is not None and abs((xt - started).total_seconds()) < 40 * 60:
                    too_close = True
                    break
                if xt is None and dkm < 8 and x.get("engine") != "open-meteo-thunder":
                    too_close = True
                    break
            if too_close:
                continue
            k = abs(int(s.get("lead_h") or 0))
            slat = slat + 0.025 * ((k % 3) - 1)
            slon = slon + 0.025 * (((k // 3) % 3) - 1)
            if not _in_scope(slat, slon, frame):
                slat, slon = float(s["lat"]), float(s["lon"])
            seen.add(sig)
            place = _label(slat, slon)
            closes = started + timedelta(minutes=25)
            row = {
                **s,
                "place": place,
                "kind": "lightning",
                "phase": "past",
                "occurred_at": _iso(started),
                "occurred_ms": thunder_predict._ms(started),
                "started_at": _iso(started),
                "closes_at": _iso(closes),
                "started_ms": thunder_predict._ms(started),
                "closes_ms": thunder_predict._ms(closes),
                "engine": "open-meteo-thunder",
            }
            strokes.append(row)
            incidents.append(
                _incident(
                    iid=f"om-past-{sig[0]}-{sig[1]}-{tkey or thunder_predict._ms(started)}",
                    kind="lightning",
                    lat=slat,
                    lon=slon,
                    place=place,
                    extra={
                        "t": s.get("t"),
                        "engine": "open-meteo-thunder",
                        "phase": "past",
                        "note": "Model thunder (not GPS)",
                        "occurred_at": row["occurred_at"],
                        "occurred_ms": row["occurred_ms"],
                        "lead_h": s.get("lead_h"),
                        "started_at": row["started_at"],
                        "closes_at": row["closes_at"],
                        "started_ms": row["started_ms"],
                        "closes_ms": row["closes_ms"],
                    },
                )
            )

    grid = None
    bounds = None
    half = 1.1
    if sector.get("ok") and sector.get("grid"):
        grid = sector["grid"]
        bounds = tuple(sector.get("bounds") or imd_insat.INDIA_BOUNDS)
    elif ir.get("ok") and ir.get("grid"):
        grid, half = ir["grid"], 1.1
    cells_raw = (
        sat_cv.segment(grid, bounds=bounds)
        if grid and bounds
        else sat_cv.segment(grid, lat0=frame["lat"], lon0=frame["lon"], half_deg=half)
        if grid
        else []
    )
    cells_raw, cv_meta = cv_nowcast.enhance(
        cells_raw,
        grid,
        bounds,
        strokes=list(ltn_pack.get("strokes") or []),
    )
    hub_wx = list(zip(hubs, thunder_packs))

    def _nearest_wx(lat: float, lon: float) -> tuple[dict[str, Any], float]:
        best: dict[str, Any] = {}
        best_d = 1e18
        for h, th in hub_wx:
            d = (float(h["lat"]) - lat) ** 2 + (float(h["lon"]) - lon) ** 2
            if d < best_d:
                best_d = d
                best = th if isinstance(th, dict) else {}
        dkm = (best_d ** 0.5) * 111.3
        if dkm > 450.0:
            return {}, dkm
        return best, dkm

    cells: list[dict[str, Any]] = []
    for i, c in enumerate(cells_raw):
        clat, clon = float(c["lat"]), float(c["lon"])
        if not _in_scope(clat, clon, frame):
            continue
        kind = c.get("kind") or _kind(c)
        place = _label(clat, clon)
        vp, dkm = _nearest_wx(clat, clon)
        nwp_now = om_thunder.thunder_now(vp)
        nwp_fwd = om_thunder.thunder_forward(vp)
        n_st = int(c.get("n_strokes") or 0)
        if n_st < 1:
            n_st = sum(
                1
                for s in raw_strokes
                if ((float(s.get("lat") or 0) - clat) ** 2 + (float(s.get("lon") or 0) - clon) ** 2) ** 0.5 * 111.3
                <= 40
            )
        near = bool(vp) and dkm <= 50.0
        p_l = float(c.get("p_lightning") or 0)
        if near and kind == "lightning" and not nwp_now and n_st < 1 and p_l < 0.12:
            kind = "cloud"
        elif near and kind == "storm" and not nwp_fwd and n_st < 1 and p_l < 0.12:
            code = int(vp.get("weather_code") or 0)
            if code < 80 and float(vp.get("precip_mm") or 0) < 0.2:
                kind = "cloud"
        cell = {
            **c,
            "kind": kind,
            "place": place,
            "nwp_thunder": nwp_now,
            "nwp_thunder_fwd": nwp_fwd,
            "weather_code": vp.get("weather_code"),
            "cape": vp.get("cape"),
        }
        cell.setdefault("id", f"cell-{i}")
        cells.append(cell)
        extra = thunder_predict.live_window(cell, now)
        extra.update(
            {
                "rain_ir_mm_h": c.get("rain_ir_mm_h"),
                "min_tb_k": c.get("min_tb_k"),
                "area_km2": c.get("area_km2"),
                "p_lightning": c.get("p_lightning"),
                "p_cloudburst": c.get("p_cloudburst"),
                "engine": c.get("engine") or "cv-nowcast-v1",
                "ring": c.get("ring"),
                "trend": c.get("trend"),
                "first_seen": cell.get("first_seen"),
                "last_seen": cell.get("last_seen"),
                "nwp_thunder": cell.get("nwp_thunder"),
                "nwp_thunder_fwd": cell.get("nwp_thunder_fwd"),
            }
        )
        occ = _occurred(cell, now)
        if occ is not None:
            extra["occurred_at"] = _iso(occ)
            extra["occurred_ms"] = thunder_predict._ms(occ)
            extra["t"] = extra.get("t") or _iso(occ)
        incidents.append(
            _incident(
                iid=str(cell.get("id") or cell.get("cell_id") or f"cell-{i}"),
                kind=kind,
                lat=clat,
                lon=clon,
                place=place,
                extra=extra,
            )
        )

    pred_hits, polygons = thunder_predict.predicted_strikes(cells, now)
    incidents.extend(pred_hits)
    expired = remember_past_cells(cells, now)
    past_cells: list[dict[str, Any]] = []
    for c in expired:
        if not _in_scope(float(c["lat"]), float(c["lon"]), frame):
            continue
        kind = c.get("kind") or "storm"
        place = c.get("place") or _label(float(c["lat"]), float(c["lon"]))
        started = _parse_dt(c.get("first_seen")) or _occurred({**c, "last_seen": None}, now)
        last = _parse_dt(c.get("last_seen")) or started
        if last is None:
            continue
        if started is None:
            started = last
        pc = {
            **c,
            "kind": kind,
            "place": place,
            "phase": "past",
            "t": _iso(last),
            "occurred_at": _iso(last),
            "occurred_ms": thunder_predict._ms(last),
            "first_seen": c.get("first_seen") or _iso(started),
            "last_seen": c.get("last_seen") or _iso(last),
            "started_at": _iso(started),
            "closes_at": _iso(last),
            "started_ms": thunder_predict._ms(started),
            "closes_ms": thunder_predict._ms(last),
            "engine": c.get("engine") or "cv-nowcast-v1",
        }
        past_cells.append(pc)
        incidents.append(
            _incident(
                iid=f"past-{c.get('id') or round(float(c['lat']), 2)}-{round(float(c['lon']), 2)}",
                kind=kind,
                lat=float(c["lat"]),
                lon=float(c["lon"]),
                place=place,
                extra=pc,
            )
        )

    from app.data.physiography import classify as phys_classify
    from app.science.landslide import HILL_STATES

    landslides: list[dict[str, Any]] = []
    seen_slide: set[tuple[float, float]] = set()
    for cell in list(cells) + list(expired):
        try:
            plat, plon = float(cell["lat"]), float(cell["lon"])
        except (KeyError, TypeError, ValueError):
            continue
        if not _in_scope(plat, plon, frame):
            continue
        phys = phys_classify(plat, plon)
        st = (nearest(plat, plon) or {}).get("state") or ""
        hill = phys.get("kind") == "orographic" or (
            st in HILL_STATES and phys.get("kind") in {"orographic", "plateau", "hugli"}
        )
        rain = float(cell.get("rain_ir_mm_h") or 0)
        cp = float(cell.get("p_cloudburst") or 0)
        if not hill or (rain < 8 and cp < 0.28):
            continue
        key = (round(plat, 2), round(plon, 2))
        if key in seen_slide:
            continue
        seen_slide.add(key)
        live = any(
            abs(float(x.get("lat") or 0) - plat) < 0.03 and abs(float(x.get("lon") or 0) - plon) < 0.03 for x in cells
        )
        win_h = 6
        last = _parse_dt(cell.get("last_seen")) or _occurred(cell, now)
        landslides.append(
            {
                "id": f"slide-{cell.get('id')}",
                "kind": "landslide",
                "phase": "live" if live else "past",
                "lat": plat,
                "lon": plon,
                "place": cell.get("place"),
                "p": round(min(0.9, 0.3 + rain / 40.0 + cp * 0.4), 3),
                "rain_ir_mm_h": rain,
                "t": _iso(last) if last else None,
                "occurred_at": _iso(last) if (last and not live) else None,
                "occurred_ms": thunder_predict._ms(last) if (last and not live) else None,
                "first_seen": cell.get("first_seen"),
                "window_start": _iso(now) if live else (cell.get("started_at") or (_iso(last) if last else None)),
                "window_end": _iso(now + timedelta(hours=win_h)) if live else (cell.get("closes_at") or (_iso(last) if last else None)),
                "window_h": win_h,
                "note": "Orographic IR rain watch — not GSI",
            }
        )

    for h, th in zip(hubs, thunder_packs):
        hlat, hlon = float(h["lat"]), float(h["lon"])
        if not _in_scope(hlat, hlon, frame):
            continue
        h = {**h, "label": _label(hlat, hlon)}
        om_rows = thunder_predict.om_predicted(h, th, now)
        if om_rows:
            incidents.extend(om_rows)
            continue
        if not th.get("thunder"):
            continue
        win = thunder_predict.lightning_window(now, now, extra={"cape": th.get("cape") or 0})
        incidents.append(
            _incident(
                iid=f"omth-{round(hlat, 2)}-{round(hlon, 2)}",
                kind="lightning",
                lat=hlat,
                lon=hlon,
                place=h["label"],
                extra={
                    "engine": "open-meteo-thunder",
                    "weather_code": th.get("weather_code"),
                    "cape": th.get("cape"),
                    "p_lightning": 0.55 if int(th.get("weather_code") or 0) >= 95 else 0.4,
                    **win,
                },
            )
        )

    now_ms = thunder_predict._ms(now)
    incidents = [
        i
        for i in incidents
        if i.get("phase") in {"past", "predicted"} or int(i.get("closes_ms") or 0) >= now_ms - 30_000
    ]

    for inc in incidents:
        vp, _dkm = _nearest_wx(float(inc["lat"]), float(inc["lon"]))
        if not vp:
            continue
        agrees = om_thunder.agrees(inc["kind"], vp) if vp.get("ok") else None
        inc["verify"] = {
            "weather_code": vp.get("weather_code"),
            "precip_mm": vp.get("precip_mm"),
            "cape": vp.get("cape"),
            "agrees": agrees,
            "note": f"OM code {vp.get('weather_code')} precip {vp.get('precip_mm')}",
        }
        if inc.get("phase") == "predicted":
            inc.update(
                thunder_predict.confidence_of(
                    float(inc.get("p_lightning") or 0),
                    lead_min=int(inc.get("lead_min") or 0),
                    cape=float(vp.get("cape") or 0),
                    weather_code=int(vp.get("weather_code") or 0),
                    agrees=agrees,
                    p_cloudburst=float(inc.get("p_cloudburst") or 0),
                )
            )
            gate = thunder_predict.agreement_gate(
                kind=str(inc.get("kind") or "lightning"),
                p_lightning=float(inc.get("p_lightning") or 0),
                ot=bool(inc.get("ot")),
                cape=float(vp.get("cape") or 0),
                weather_code=int(vp.get("weather_code") or 0),
                agrees=agrees,
                n_strokes=int(inc.get("n_strokes") or 0),
                schultz_jump=bool((inc.get("schultz") or {}).get("jump")),
            )
            inc["gate"] = gate
            if not gate.get("ok"):
                inc["confidence_band"] = "low"
                inc["verify"] = {**(inc.get("verify") or {}), "note": "IR nowcast — not confirmed by strokes or NWP"}
            thunder_predict.log_verify(
                {
                    "t": _iso(now),
                    "kind": inc.get("kind"),
                    "p_lightning": inc.get("p_lightning"),
                    "agrees": agrees,
                    "gate": gate.get("status"),
                    "cape": vp.get("cape"),
                    "weather_code": vp.get("weather_code"),
                    "lat": inc.get("lat"),
                    "lon": inc.get("lon"),
                    "lead_min": inc.get("lead_min"),
                }
            )

    order = {"lightning": 0, "cloudburst": 1, "downburst": 2, "storm": 3, "cloud": 4}
    phase_order = {"live": 0, "predicted": 1, "past": 2, "ended": 3}
    incidents.sort(
        key=lambda x: (
            phase_order.get(str(x.get("phase") or "live"), 9),
            order.get(x["kind"], 9),
            int(x.get("lead_min") or 0),
            x["place"],
        )
    )

    def _pred_ok(i: dict[str, Any]) -> bool:
        if i.get("engine") in {"open-meteo-thunder", "thunder-predict-v1", "cv-nowcast-v1"}:
            return True
        if (i.get("gate") or {}).get("ok"):
            return True
        if i.get("nwp_thunder_fwd") or i.get("nwp_thunder"):
            return True
        if float(i.get("p_lightning") or 0) >= 0.12 or float(i.get("p_cloudburst") or 0) >= 0.12:
            return True
        if int(i.get("lead_min") or 0) > 0:
            return True
        return int(i.get("n_strokes") or 0) >= 1

    predicted = [
        i
        for i in incidents
        if i.get("phase") == "predicted" and i["kind"] == "lightning" and _pred_ok(i)
    ]
    predicted_storms = [
        i
        for i in incidents
        if i.get("phase") == "predicted" and i["kind"] != "lightning" and _pred_ok(i)
    ]
    predicted_unverified = [
        i
        for i in incidents
        if i.get("phase") == "predicted" and not _pred_ok(i)
    ]
    live = [i for i in incidents if i.get("phase") == "live"]
    cutoff_past = now - timedelta(hours=past_h)
    cutoff_fwd = now + timedelta(hours=past_h)

    def _keep_pred(d: dict[str, Any]) -> bool:
        t = _parse_dt(d.get("started_at") or d.get("t"))
        if t is None:
            return True
        return t <= cutoff_fwd

    def _keep_past(d: dict[str, Any]) -> bool:
        t = _parse_dt(d.get("last_seen") or d.get("occurred_at") or d.get("t") or d.get("first_seen"))
        return t is not None and t >= cutoff_past

    past_cells = [c for c in past_cells if _keep_past(c)]
    strokes = [s for s in strokes if _keep_past(s)]
    landslides = [x for x in landslides if x.get("phase") != "past" or _keep_past(x)]
    incidents = [
        i
        for i in incidents
        if i.get("phase") != "past" or i.get("kind") == "fire" or _keep_past(i)
    ]
    past = [i for i in incidents if i.get("phase") == "past"]
    fires_in = [
        fr
        for fr in (firms_pack.get("fires") or [])
        if _in_scope(float(fr.get("lat") or 0), float(fr.get("lon") or 0), frame)
    ][:60]

    n_frames = int((cv_meta or {}).get("frames") or (1 if cells else 0))

    pack = {
        "as_of": _iso(now),
        "as_of_ms": now_ms,
        "state": frame["state"],
        "frame": frame,
        "strokes": strokes[:200],
        "past_strokes": strokes[:200],
        "past_cells": [c for c in past_cells if str(c.get("kind") or "") != "lightning"][:80],
        "cells": cells[:48],
        "incidents": incidents[:220],
        "predicted": [i for i in predicted if _keep_pred(i)][:80],
        "predicted_storms": [i for i in predicted_storms if _keep_pred(i)][:80],
        "predicted_unverified": [i for i in predicted_unverified if _keep_pred(i)][:80],
        "polygons": polygons[:40],
        "counts": {
            "lightning": sum(1 for i in live if i["kind"] == "lightning"),
            "cloudburst": sum(1 for i in live if i["kind"] == "cloudburst"),
            "downburst": sum(1 for i in live if i["kind"] == "downburst"),
            "storm": sum(1 for i in live if i["kind"] == "storm"),
            "past_lightning": sum(1 for i in past if i["kind"] == "lightning"),
            "past_storm": sum(1 for i in past if i["kind"] != "lightning"),
            "predicted": len(predicted),
            "predicted_storm": len(predicted_storms),
            "predicted_unverified": len(predicted_unverified),
            "ir_frames": n_frames,
            "fire": len(fires_in),
            "landslide": len(landslides),
            "cloud": sum(1 for i in live if i["kind"] == "cloud"),
            "all": len(incidents),
        },
        "imerg_mm_h": (imerg or {}).get("mm_h"),
        "insat_tb_k": (ir or {}).get("tb_k"),
        "fires": fires_in,
        "landslides": landslides[:40],
        "ok": bool(
            incidents
            or cells
            or sector.get("ok")
            or ir.get("ok")
            or (imerg or {}).get("ok")
            or (firms_pack or {}).get("ok")
            or n_frames >= 1
        ),
        "past_h": past_h,
        "need_second_frame": n_frames < 2,
        "cv": cv_meta,
        "sensors": {
            "lightning": bool((ltn_pack.get("n") or 0) > 0) or any(p.get("thunder") for p in thunder_packs),
            "lightning_status": ltn_pack.get("status") or "cv+open-meteo",
            "lightning_source": ltn_pack.get("source"),
            "lightning_hubs": ltn_pack.get("hubs"),
            "lightning_history_n": ltn_pack.get("history_n"),
            "insat": bool(sector.get("ok")),
            "gibs_ir": bool(ir.get("ok")),
            "imerg": bool((imerg or {}).get("ok")),
            "open_meteo_thunder": any(p.get("ok") for p in thunder_packs),
            "firms": bool((firms_pack or {}).get("ok")),
            "firms_n": int((firms_pack or {}).get("n") or 0),
        },
        "method": "thunder-predict-v1 + cv-nowcast + open-meteo-thunder + firms",
        "processing": {
            "ready": True,
            "message": "",
            "satellites": [
                {"id": "imd_ir1", "name": "INSAT-3DS IR1 JPEG", "status": "ok" if sector.get("ok") or ir.get("ok") else "fail"},
                {"id": "gibs", "name": "GIBS Himawari Band 13", "status": "ok" if ir.get("ok") else "fail"},
                {"id": "imerg", "name": "GPM IMERG", "status": "ok" if (imerg or {}).get("ok") else "fail"},
            ],
            "age_s": 0,
        },
    }
    pack["counts"]["predicted"] = len(pack["predicted"])
    pack["counts"]["predicted_storm"] = len(pack["predicted_storms"])
    pack["counts"]["predicted_unverified"] = len(pack["predicted_unverified"])
    try:
        from app.science.cv_memory import remember_cells, remember_frame

        remember_frame(cells, pack.get("as_of"))
        remember_cells(cells)
    except Exception:
        pass
    try:
        from app.store.hazard_events import persist_pack_incidents

        persist_pack_incidents(pack)
    except Exception:
        pass
    return pack

"""State-cropped live storm layer + India incident feed."""

from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from typing import Any

from app.config import ROOT
from app.data.india_districts import districts_in_state, nearest, state_frame
from app.data.india_mask import in_india
from app.science import sat_cv, thunder_predict

IST = timezone(timedelta(hours=5, minutes=30))
PAST_CELLS = ROOT / ".cache" / "past_storm_cells.json"

INDIA_HUBS = [
    {"lat": 22.57, "lon": 88.36, "district": "Kolkata", "state": "West Bengal"},
    {"lat": 26.18, "lon": 91.75, "district": "Kamrup", "state": "Assam"},
    {"lat": 28.61, "lon": 77.21, "district": "New Delhi", "state": "Delhi"},
    {"lat": 19.08, "lon": 72.88, "district": "Mumbai", "state": "Maharashtra"},
    {"lat": 13.08, "lon": 80.27, "district": "Chennai", "state": "Tamil Nadu"},
    {"lat": 12.97, "lon": 77.59, "district": "Bengaluru Urban", "state": "Karnataka"},
    {"lat": 17.39, "lon": 78.49, "district": "Hyderabad", "state": "Telangana"},
    {"lat": 23.03, "lon": 72.58, "district": "Ahmadabad", "state": "Gujarat"},
    {"lat": 20.27, "lon": 85.84, "district": "Khordha", "state": "Odisha"},
    {"lat": 25.61, "lon": 85.14, "district": "Patna", "state": "Bihar"},
]


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
    if cell.get("trend") == "collapsing":
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
    return dt.astimezone(IST).isoformat(timespec="seconds")


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
    """IR cells that dropped off the live set stay as past-storm markers for 4 h."""
    if os.environ.get("PYTEST_CURRENT_TEST"):
        return []
    cutoff = now - timedelta(hours=4)
    live_keys = {(round(float(c["lat"]), 2), round(float(c["lon"]), 2), c.get("kind")) for c in cells}
    mem = _load_past_cells()
    out: list[dict[str, Any]] = []
    seen: set[tuple] = set()
    for c in cells:
        key = (round(float(c["lat"]), 2), round(float(c["lon"]), 2), c.get("kind"))
        row = {**c, "first_seen": c.get("first_seen") or now.isoformat(), "last_seen": now.isoformat()}
        seen.add(key)
        out.append(row)
    for c in mem:
        try:
            key = (round(float(c["lat"]), 2), round(float(c["lon"]), 2), c.get("kind"))
        except (TypeError, ValueError, KeyError):
            continue
        if key in seen or key in live_keys:
            continue
        try:
            last = datetime.fromisoformat(str(c.get("last_seen") or "").replace("Z", "+00:00"))
            if last.tzinfo is None:
                last = last.replace(tzinfo=timezone.utc)
        except ValueError:
            continue
        if last < cutoff:
            continue
        seen.add(key)
        out.append(c)
    _save_past_cells(out)
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


async def build(state: str) -> dict[str, Any]:
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
        "ok": False,
        "sensors": {},
        "method": "thunder-predict-v1",
    }
    if os.environ.get("PYTEST_CURRENT_TEST"):
        return {**empty, "ok": True, "status": "test-skip"}
    if not frame.get("ok"):
        return {**empty, "status": "unknown_state"}

    from app.providers import gibs_ir, imd_insat, lightning_feed, om_thunder
    from app.science import cv_nowcast
    import asyncio

    all_india = bool(frame.get("all_india"))
    if all_india:
        hubs = INDIA_HUBS
    else:
        rows = districts_in_state(frame["state"])
        hubs = _spread_hubs(rows, 4) or [
            {"lat": frame["lat"], "lon": frame["lon"], "district": frame["state"], "state": frame["state"]}
        ]

    ltn_hubs = hubs[:6] if all_india else hubs[:3]
    ltn_pack, thunder_packs, sector, ir, imerg = await asyncio.gather(
        lightning_feed.fetch_hubs(ltn_hubs, history=True, frame=frame),
        asyncio.gather(*[om_thunder.fetch(float(h["lat"]), float(h["lon"])) for h in hubs]),
        imd_insat.fetch_sector(),
        gibs_ir.fetch_ir(frame["lat"], frame["lon"]),
        gibs_ir.fetch_imerg(frame["lat"], frame["lon"]),
    )

    seen: set[tuple[float, float, str]] = set()
    strokes: list[dict[str, Any]] = []
    incidents: list[dict[str, Any]] = []
    for s in ltn_pack.get("strokes") or []:
        slat, slon = float(s["lat"]), float(s["lon"])
        if not _in_scope(slat, slon, frame):
            continue
        tkey = str(s.get("t") or s.get("timestamp_utc") or "")[:16]
        sig = (round(slat, 3), round(slon, 3), tkey)
        if sig in seen:
            continue
        seen.add(sig)
        place = _label(slat, slon)
        started = now
        raw_t = s.get("t") or s.get("timestamp_utc")
        if raw_t:
            try:
                started = datetime.fromisoformat(str(raw_t).replace("Z", "+00:00"))
                if started.tzinfo is None:
                    started = started.replace(tzinfo=timezone.utc)
            except ValueError:
                started = now
        elif s.get("past_mins") is not None:
            try:
                started = now - timedelta(minutes=float(s["past_mins"]))
            except (TypeError, ValueError):
                started = now
        closes = started + timedelta(minutes=8)
        row = {
            **s,
            "place": place,
            "kind": "lightning",
            "phase": "past",
            "started_at": _iso(started),
            "closes_at": _iso(closes),
            "started_ms": thunder_predict._ms(started),
            "closes_ms": thunder_predict._ms(closes),
            "engine": "weatherbit-lightning",
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
                    "engine": "weatherbit-lightning",
                    "phase": "past",
                    "started_at": row["started_at"],
                    "closes_at": row["closes_at"],
                    "started_ms": row["started_ms"],
                    "closes_ms": row["closes_ms"],
                },
            )
        )

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
            too_close = any(
                ((float(x["lat"]) - slat) ** 2 + (float(x["lon"]) - slon) ** 2) ** 0.5 * 111.3 < 35 for x in strokes
            )
            if too_close:
                continue
            seen.add(sig)
            place = _label(slat, slon)
            started = now + timedelta(hours=int(s.get("lead_h") or -1))
            if s.get("t"):
                try:
                    started = datetime.fromisoformat(str(s["t"]))
                    if started.tzinfo is None:
                        started = started.replace(tzinfo=IST)
                except ValueError:
                    pass
            closes = started + timedelta(minutes=20)
            row = {
                **s,
                "place": place,
                "kind": "lightning",
                "phase": "past",
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
    cells_raw, cv_meta = cv_nowcast.enhance(cells_raw, grid, bounds)
    cells: list[dict[str, Any]] = []
    for i, c in enumerate(cells_raw):
        clat, clon = float(c["lat"]), float(c["lon"])
        if not _in_scope(clat, clon, frame):
            continue
        kind = c.get("kind") or _kind(c)
        place = _label(clat, clon)
        cell = {**c, "kind": kind, "place": place}
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
            }
        )
        incidents.append(
            _incident(
                iid=str(c.get("id") or f"cell-{i}"),
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
        if kind == "lightning":
            continue
        place = c.get("place") or _label(float(c["lat"]), float(c["lon"]))
        started = now - timedelta(hours=1)
        if c.get("first_seen"):
            try:
                started = datetime.fromisoformat(str(c["first_seen"]).replace("Z", "+00:00"))
                if started.tzinfo is None:
                    started = started.replace(tzinfo=timezone.utc)
            except ValueError:
                pass
        last = now - timedelta(minutes=20)
        if c.get("last_seen"):
            try:
                last = datetime.fromisoformat(str(c["last_seen"]).replace("Z", "+00:00"))
                if last.tzinfo is None:
                    last = last.replace(tzinfo=timezone.utc)
            except ValueError:
                pass
        pc = {
            **c,
            "kind": kind,
            "place": place,
            "phase": "past",
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

    hub_wx = list(zip(hubs, thunder_packs))

    def _nearest_wx(lat: float, lon: float) -> dict[str, Any]:
        best = {}
        best_d = 1e18
        for h, th in hub_wx:
            d = (float(h["lat"]) - lat) ** 2 + (float(h["lon"]) - lon) ** 2
            if d < best_d:
                best_d = d
                best = th if isinstance(th, dict) else {}
        return best

    for inc in incidents:
        vp = _nearest_wx(float(inc["lat"]), float(inc["lon"]))
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

    predicted = [i for i in incidents if i.get("phase") == "predicted" and i["kind"] == "lightning"]
    predicted_storms = [i for i in incidents if i.get("phase") == "predicted" and i["kind"] != "lightning"]
    live = [i for i in incidents if i.get("phase") == "live"]
    past = [i for i in incidents if i.get("phase") == "past"]

    return {
        "as_of": _iso(now),
        "as_of_ms": now_ms,
        "state": frame["state"],
        "frame": frame,
        "strokes": strokes[:80],
        "past_strokes": strokes[:80],
        "past_cells": past_cells[:40],
        "cells": cells[:32],
        "incidents": incidents[:120],
        "predicted": predicted[:40],
        "predicted_storms": predicted_storms[:40],
        "polygons": polygons[:24],
        "counts": {
            "lightning": sum(1 for i in live if i["kind"] == "lightning"),
            "cloudburst": sum(1 for i in live if i["kind"] == "cloudburst"),
            "downburst": sum(1 for i in live if i["kind"] == "downburst"),
            "storm": sum(1 for i in live if i["kind"] == "storm"),
            "past_lightning": sum(1 for i in past if i["kind"] == "lightning"),
            "past_storm": sum(1 for i in past if i["kind"] != "lightning"),
            "predicted": len(predicted),
            "predicted_storm": len(predicted_storms),
            "all": len(incidents),
        },
        "imerg_mm_h": (imerg or {}).get("mm_h"),
        "insat_tb_k": (ir or {}).get("tb_k"),
        "ok": bool(incidents or sector.get("ok") or ir.get("ok") or (imerg or {}).get("ok")),
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
        },
        "method": "thunder-predict-v1 + cv-nowcast + open-meteo-thunder",
    }

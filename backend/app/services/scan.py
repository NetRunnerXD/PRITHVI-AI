"""Lightweight multi-district forecasts. Used by the agent to rank / list a state."""

from __future__ import annotations

import asyncio
from typing import Any

from app.data.india_districts import all_districts, districts_in_state
from app.providers import open_meteo

_SEM = asyncio.Semaphore(8)


def _clip(x: float, lo: float = 0.0, hi: float = 100.0) -> float:
    return max(lo, min(hi, x))


def _daily_sum(om: dict, n: int = 3) -> float:
    vals = (om.get("daily") or {}).get("precipitation_sum") or []
    total = 0.0
    for v in vals[:n]:
        try:
            total += float(v or 0)
        except (TypeError, ValueError):
            pass
    return total


def _soil(om: dict) -> float:
    vals = (om.get("hourly") or {}).get("soil_moisture_0_to_7cm") or []
    for v in vals:
        try:
            return float(v)
        except (TypeError, ValueError):
            continue
    return 0.28


def _tmax(om: dict) -> float:
    vals = (om.get("daily") or {}).get("temperature_2m_max") or []
    try:
        return float(vals[0])
    except (TypeError, ValueError, IndexError):
        return 30.0


def _flood_score(precip_3d: float, soil: float, lat: float, lon: float) -> int:
    low_elev = lat < 27.5 and lon > 80
    rain = _clip((precip_3d - 8) / 70 * 100)
    sat = _clip((soil - 0.22) / 0.20 * 100)
    elev = 55 if low_elev else 20
    return int(round(_clip(0.55 * rain + 0.30 * sat + 0.15 * elev)))


def _drought_score(precip_3d: float, soil: float) -> int:
    return int(round(_clip((18 - precip_3d) / 18 * 55 + (0.26 - soil) / 0.14 * 45)))


async def _one(row: dict) -> dict[str, Any]:
    async with _SEM:
        try:
            om = await open_meteo.forecast(row["lat"], row["lon"])
            p3 = round(_daily_sum(om, 3), 1)
            soil = round(_soil(om), 3)
            tmax = round(_tmax(om), 1)
            flood = _flood_score(p3, soil, row["lat"], row["lon"])
            drought = _drought_score(p3, soil)
            return {
                "id": row["id"],
                "district": row["district"],
                "state": row["state"],
                "label": row["label"],
                "lat": row["lat"],
                "lon": row["lon"],
                "precip_3d_mm": p3,
                "soil_m3m3": soil,
                "temp_max_c": tmax,
                "flood_score": flood,
                "drought_score": drought,
                "irrigation_need": drought if p3 < 8 else max(0, drought - 30),
                "ok": True,
            }
        except Exception as exc:
            return {
                "id": row["id"],
                "district": row["district"],
                "state": row["state"],
                "label": row["label"],
                "error": str(exc),
                "ok": False,
            }


def _sort_key(metric: str):
    metric = (metric or "flood").lower()
    if metric in {"rain", "precip", "rainfall"}:
        return lambda r: -float(r.get("precip_3d_mm") or 0)
    if metric in {"drought", "dry"}:
        return lambda r: -float(r.get("drought_score") or 0)
    if metric in {"heat", "temp"}:
        return lambda r: -float(r.get("temp_max_c") or 0)
    if metric in {"irrigation", "irrigate"}:
        return lambda r: -float(r.get("irrigation_need") or 0)
    return lambda r: -float(r.get("flood_score") or 0)


async def rank_districts(state: str | None, metric: str = "flood", limit: int = 40) -> dict[str, Any]:
    rows = districts_in_state(state) if state else list(all_districts())
    note = None
    if state and not rows:
        return {
            "state": state,
            "metric": metric,
            "count": 0,
            "ranked": [],
            "note": f"No gazetteer districts for {state}. Pass an Indian state, not a town.",
            "method": "open-meteo 3-day precip + soil + elevation proxy (local-ml-v1)",
            "error": "unknown_state",
        }
    if not state and len(rows) > 80:
        note = "India-wide scan uses the bundled gazetteer (HQ towns). Pass a state for a complete district list."
    scored = await asyncio.gather(*[_one(r) for r in rows])
    ok = [r for r in scored if r.get("ok")]
    ok.sort(key=_sort_key(metric))
    top = ok[: max(1, min(int(limit or 40), 80))]
    return {
        "state": state or "India (gazetteer)",
        "metric": metric,
        "count": len(ok),
        "ranked": top,
        "note": note,
        "method": "open-meteo 3-day precip + soil + elevation proxy (local-ml-v1)",
    }


async def rank_states(metric: str = "flood", limit: int = 20) -> dict[str, Any]:
    """One HQ district per state — India-wide weather/flood ranking, not tourism."""
    seen: set[str] = set()
    reps: list[dict] = []
    for row in all_districts():
        st = row["state"]
        if st in seen:
            continue
        seen.add(st)
        reps.append(row)
    scored = await asyncio.gather(*[_one(r) for r in reps])
    ok = [r for r in scored if r.get("ok")]
    ok.sort(key=_sort_key(metric))
    top = ok[: max(1, min(int(limit or 20), 36))]
    return {
        "need": "states_weather",
        "scope": "india-states",
        "metric": metric,
        "count": len(ok),
        "ranked": top,
        "method": "open-meteo 3-day precip + soil + elevation proxy at one gazetteer HQ per state",
        "note": "This is a weather/flood ranking, not a tourist or pet-visit ranking.",
    }


async def predict_one(row: dict) -> dict[str, Any]:
    return await _one(row)

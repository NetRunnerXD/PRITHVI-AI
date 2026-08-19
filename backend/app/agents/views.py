"""LLM-facing JSON. Forbidden rates never leave this module."""

from __future__ import annotations

from typing import Any

FORBIDDEN_KEYS = frozenset(
    {
        "sat",
        "gap",
        "playhead",
        "pred_series",
        "innovations",
        "obs_knots",
        "history",
        "formula",
        "mae",
        "last_error_mm_h",
    }
)


def strip_forbidden(obj: Any) -> Any:
    if isinstance(obj, dict):
        return {k: strip_forbidden(v) for k, v in obj.items() if k not in FORBIDDEN_KEYS}
    if isinstance(obj, list):
        return [strip_forbidden(v) for v in obj]
    return obj


def compact_nowcast(nc: dict[str, Any] | None) -> dict[str, Any]:
    pack = nc or {}
    locked = pack.get("locked") or {}
    return strip_forbidden(
        {
            "nowcast": locked,
            "clock": pack.get("clock"),
            "pump": pack.get("pump"),
            "access": pack.get("access"),
            "ponding": pack.get("ponding"),
            "kal": pack.get("kal"),
            "tide": pack.get("tide"),
            "cost": pack.get("cost"),
            "air": pack.get("air"),
            "labour": pack.get("labour"),
            "actions": pack.get("actions") or [],
            "speech": (pack.get("speech") or {}).get("heard"),
            "convective": pack.get("convective"),
            "note": locked.get("engine_note") or pack.get("note"),
            "widget": "nowcast",
        }
    )


def compact_science(sci: dict[str, Any] | None) -> dict[str, Any]:
    src = sci or {}
    keys = (
        "hysteresis",
        "regret",
        "phenology",
        "monsoon",
        "cwc",
        "vernacular",
        "blindspot",
        "water_balance",
        "bandit",
        "livelihood",
        "market_lock",
    )
    return strip_forbidden({k: src[k] for k in keys if src.get(k) is not None})


def snapshot_index(snap: Any) -> dict[str, Any]:
    """1–2k start-of-turn card. Locked nowcast only."""
    cur = snap.descriptive.current
    pred = snap.predictive
    nc = ((snap.science or {}).get("nowcast") or {})
    locked = nc.get("locked") or {}
    current = {
        "temp_c": cur.temp_c,
        "sky_label": cur.sky_label,
        "soil_moisture_m3m3": cur.soil_moisture_m3m3,
        "aqi": cur.aqi,
        "aqi_category": cur.aqi_category,
        "aqi_station": cur.aqi_station,
        "precip_1h_mm": cur.precip_1h_mm,
    }
    return strip_forbidden(
        {
            "location": snap.location.model_dump(),
            "current": current,
            "predictive": {
                "precip_next_3d_mm": pred.precip_next_3d_mm,
                "precip_7d_mm": pred.precip_7d_mm,
                "water_balance_7d_mm": pred.water_balance_7d_mm,
                "et0_7d_mm": getattr(pred, "et0_7d_mm", None),
            },
            "risks": [{"id": r.id, "score_pct": r.score_pct, "severity": r.severity} for r in snap.risks],
            "nowcast": locked,
            "warnings": [
                {"title": w.title, "hazard": w.hazard, "severity": w.severity}
                for w in (snap.prescriptive.warnings or [])[:5]
            ],
            "actions": [
                {"id": a.id, "action": a.action, "template_id": a.template_id}
                for a in (snap.prescriptive.actions or [])[:6]
            ],
            "sources": snap.sources,
            "provider_status": snap.provider_status,
        }
    )


def compact_tool(name: str, payload: Any) -> Any:
    if not isinstance(payload, dict):
        return payload
    if name == "get_science_pack":
        return {"science": compact_science(payload.get("science")), "widget": payload.get("widget")}
    if name == "get_nowcast":
        return strip_forbidden(payload)
    if name == "rank_districts":
        return {
            "state": payload.get("state"),
            "metric": payload.get("metric"),
            "method": payload.get("method"),
            "count": payload.get("count"),
            "ranked": [
                {
                    "district": r.get("district"),
                    "flood_score": r.get("flood_score"),
                    "precip_3d_mm": r.get("precip_3d_mm"),
                    "drought_score": r.get("drought_score"),
                    "soil_m3m3": r.get("soil_m3m3"),
                    "temp_max_c": r.get("temp_max_c"),
                }
                for r in (payload.get("ranked") or [])[:20]
            ],
        }
    if name == "list_districts":
        return {
            "state": payload.get("state"),
            "count": payload.get("count"),
            "names": [d.get("district") for d in (payload.get("districts") or [])]
            or payload.get("names"),
        }
    if name == "get_state_mandi":
        districts = payload.get("districts") or {}
        return {
            "state": payload.get("state"),
            "status": payload.get("status"),
            "districts": {k: v[:4] for k, v in list(districts.items())[:25]},
        }
    if name == "get_hazard_watch":
        live = payload.get("live") or {}
        keep = {k: live.get(k) for k in ("sky", "flood", "air", "marine") if k in live}
        if live.get("quakes"):
            keep["quakes"] = live["quakes"][:3]
        if live.get("tsunami"):
            keep["tsunami"] = live["tsunami"][:3]
        return strip_forbidden(
            {
                "warnings": payload.get("warnings"),
                "live": keep,
                "provider_status": payload.get("provider_status"),
                "note": payload.get("note"),
                "widget": payload.get("widget"),
            }
        )
    return strip_forbidden(payload)

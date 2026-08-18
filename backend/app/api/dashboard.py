from fastapi import APIRouter, Depends, Query

from app.api.deps import loc_from_query
from app.schemas.location import Location
from app.services.compare import compare
from app.services.location_svc import list_districts, list_states
from app.services.scan import rank_districts
from app.services.snapshot import build_snapshot
from app.tools import build_registry

router = APIRouter()


@router.get("/dashboard")
async def dashboard(loc: Location = Depends(loc_from_query), locale: str = "en"):
    snap = await build_snapshot(loc, locale)
    return snap.model_dump()


@router.get("/forecast")
async def forecast(loc: Location = Depends(loc_from_query)):
    snap = await build_snapshot(loc)
    return {
        "location": snap.location.model_dump(),
        "predictive": snap.predictive.model_dump(),
        "descriptive": snap.descriptive.model_dump(),
        "sources": snap.sources,
    }


@router.get("/predictions")
async def predictions(loc: Location = Depends(loc_from_query), source: str = "both"):
    snap = await build_snapshot(loc)
    dual = snap.predictions or {}
    if source == "ours":
        return {"location": snap.location.model_dump(), "active": "ours", **(dual.get("ours") or {})}
    if source == "trusted":
        return {"location": snap.location.model_dump(), "active": "trusted", **(dual.get("trusted") or {})}
    return {"location": snap.location.model_dump(), "active": "both", **dual}


@router.get("/outlook")
async def outlook(loc: Location = Depends(loc_from_query)):
    snap = await build_snapshot(loc)
    return {
        "location": snap.location.model_dump(),
        "outlook_days": snap.predictive.outlook_days,
        "precip_7d_mm": snap.predictive.precip_7d_mm,
        "et0_7d_mm": snap.predictive.et0_7d_mm,
        "water_balance_7d_mm": snap.predictive.water_balance_7d_mm,
        "irrigate_dates": snap.predictive.irrigate_dates,
        "flood_watch_dates": snap.predictive.flood_watch_dates,
    }


@router.get("/risks")
async def risks(loc: Location = Depends(loc_from_query)):
    snap = await build_snapshot(loc)
    return {"location": snap.location.model_dump(), "risks": [r.model_dump() for r in snap.risks]}


@router.get("/science")
async def science_api(loc: Location = Depends(loc_from_query)):
    snap = await build_snapshot(loc)
    return {"location": snap.location.model_dump(), "science": snap.science or {}}


@router.get("/nowcast")
async def nowcast_api(loc: Location = Depends(loc_from_query)):
    snap = await build_snapshot(loc)
    nc = (snap.science or {}).get("nowcast") or {}
    return {
        "location": snap.location.model_dump(),
        "nowcast": nc.get("locked") or {},
        "hours": nc.get("hours") or [],
        "observed": nc.get("observed") or [],
        "regime": nc.get("regime"),
        "clock": nc.get("clock"),
        "pump": nc.get("pump"),
        "access": nc.get("access"),
        "ponding": nc.get("ponding"),
        "kal": nc.get("kal"),
        "tide": nc.get("tide"),
        "air": nc.get("air"),
        "actions": nc.get("actions") or [],
        "method": nc.get("method"),
    }


@router.get("/insights")
async def insights(loc: Location = Depends(loc_from_query)):
    snap = await build_snapshot(loc)
    return {
        "warnings": [w.model_dump() for w in snap.prescriptive.warnings],
        "actions": [a.model_dump() for a in snap.prescriptive.actions],
        "diagnostic": snap.diagnostic.model_dump(),
        "vegetation": snap.vegetation,
    }


@router.get("/compare")
async def compare_api(a: str = Query(min_length=2), b: str = Query(min_length=2)):
    return await compare(a, b)


@router.get("/states")
async def states_api():
    return {"states": list_states()}


@router.get("/districts")
async def districts_api(state: str | None = None):
    rows = list_districts(state)
    return {"state": state or "India", "count": len(rows), "districts": [r.model_dump() for r in rows]}


@router.get("/scan")
async def scan_api(state: str = Query(min_length=2), metric: str = "flood", limit: int = 30):
    return await rank_districts(state, metric=metric, limit=limit)


@router.get("/agent/tools")
async def list_tools(loc: Location = Depends(loc_from_query)):
    snap = await build_snapshot(loc)
    reg = build_registry(snap)
    return {
        "tools": [
            {"name": t.name, "description": t.description, "widget": t.widget_path}
            for t in reg.tools.values()
        ]
    }


@router.post("/brief")
async def brief(loc: Location = Depends(loc_from_query), locale: str = "en"):
    from app.services.snapshot import primary_reply

    snap = await build_snapshot(loc, locale)
    text, tid, slots = primary_reply(snap, locale, "general")
    return {
        "location": snap.location.model_dump(),
        "brief": text,
        "template_id": tid,
        "slots": slots,
        "risks": [r.model_dump() for r in snap.risks],
        "outlook_days": snap.predictive.outlook_days,
    }

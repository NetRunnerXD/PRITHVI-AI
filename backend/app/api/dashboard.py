from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response

router = APIRouter()

from app.api.deps import loc_from_query
from app.schemas.location import Location
from app.services.compare import compare
from app.services.location_svc import list_districts, list_states
from app.services.scan import rank_districts
from app.services.snapshot import build_snapshot
from app.tools import build_registry


@router.get("/sat/imd-asia")
async def imd_asia_jpeg():
    """Same-origin INSAT Asia-sector JPEG so Leaflet ImageOverlay is not blocked by CORS."""
    from app.providers.imd_insat import fetch_jpeg

    body, _url, status = await fetch_jpeg()
    if not body:
        return Response(status_code=502, content=f"imd jpeg {status}".encode())
    return Response(
        content=body,
        media_type="image/jpeg",
        headers={"Cache-Control": "public, max-age=120", "Access-Control-Allow-Origin": "*"},
    )


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


@router.get("/forecast/hourly")
async def forecast_hourly(
    loc: Location = Depends(loc_from_query),
    date: str | None = Query(default=None, description="YYYY-MM-DD IST"),
):
    snap = await build_snapshot(loc)
    hours = list(snap.predictive.hourly or [])
    days = sorted({str(h.get("date")) for h in hours if h.get("date")})
    if date:
        hours = [h for h in hours if str(h.get("date")) == date[:10]]
    return {
        "location": snap.location.model_dump(),
        "date": (date or "")[:10] or None,
        "dates": days,
        "hours": hours,
        "n": len(hours),
        "source": "open-meteo hourly",
        "note": "Model forecast, not a gauge. Hours are Asia/Kolkata.",
    }


@router.get("/blend")
@router.get("/blend/weights")
async def blend_weights(loc: Location = Depends(loc_from_query)):
    snap = await build_snapshot(loc)
    hybrid = (snap.predictions or {}).get("hybrid") or {}
    from app.providers.mosdac import status as mosdac_status

    return {
        "location": snap.location.model_dump(),
        "weights": hybrid.get("weights") or {},
        "members": hybrid.get("members") or [],
        "method": hybrid.get("method"),
        "attribution": hybrid.get("attribution"),
        "guidance_only": True,
        "mosdac": mosdac_status(),
        "days": hybrid.get("days") or [],
        "hazards": hybrid.get("hazards") or {},
    }


@router.get("/blend/hazards")
async def blend_hazards(loc: Location = Depends(loc_from_query)):
    snap = await build_snapshot(loc)
    hybrid = (snap.predictions or {}).get("hybrid") or {}
    return {
        "location": snap.location.model_dump(),
        "guidance_only": True,
        "hazards": hybrid.get("hazards") or {},
        "days": hybrid.get("days") or [],
    }


@router.get("/vera/parameters")
async def vera_parameters(loc: Location = Depends(loc_from_query)):
    snap = await build_snapshot(loc)
    vera = (snap.predictions or {}).get("vera") or {}
    return {
        "location": snap.location.model_dump(),
        "parameters": vera.get("parameters"),
        "fusion": {k: (vera.get("fusion") or {}).get(k) for k in ("method", "q50", "q95", "q99", "eqmn")},
        "train": _vera_train_status(),
    }


@router.post("/vera/train")
async def vera_train(epochs: int = Query(default=20, ge=1, le=200)):
    from app.ml.train import eqrn, swin_unet

    eq = eqrn.train(epochs=epochs)
    sw = swin_unet.train(epochs=min(epochs, 30))
    return {"eqrn": eq, "swin": sw}


@router.get("/vera/train")
async def vera_train_status():
    return _vera_train_status()


def _vera_train_status() -> dict:
    from app.ml.train import eqrn, swin_unet

    return {"eqrn": eqrn.status(), "swin": swin_unet.status()}


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
        "hourly": snap.predictive.hourly,
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
        "gap": nc.get("gap"),
        "playhead": nc.get("playhead"),
        "actions": nc.get("actions") or [],
        "method": nc.get("method"),
        "live_note": nc.get("live_note"),
        "sat": nc.get("sat") or {},
        "convective": nc.get("convective") or {},
        "sat_live": nc.get("sat_live") or {},
    }


def _nowcast_live_body(snap) -> dict:
    from app.science.live import playhead as make_playhead

    nc = (snap.science or {}).get("nowcast") or {}
    ph = make_playhead(nc, loc=snap.location)
    return {
        "location": snap.location.model_dump(),
        "as_of": ph.get("t"),
        "knots": nc.get("hours") or [],
        "observed": nc.get("observed") or [],
        "gap": nc.get("gap") or {},
        "playhead": ph,
        "clock": nc.get("clock"),
        "pump": nc.get("pump"),
        "access": nc.get("access"),
        "ponding": nc.get("ponding"),
        "kal": nc.get("kal"),
        "tide": nc.get("tide"),
        "locked": nc.get("locked") or {},
        "actions": nc.get("actions") or [],
        "provenance": (snap.science or {}).get("provenance"),
        "cwc": (snap.science or {}).get("cwc"),
        "port": (snap.science or {}).get("port"),
        "phys": nc.get("phys") or (snap.science or {}).get("phys"),
        "monsoon": (snap.science or {}).get("monsoon"),
        "verify": (snap.science or {}).get("verify"),
        "engine_note": (nc.get("locked") or {}).get("engine_note"),
        "sat": nc.get("sat") or {},
        "convective": nc.get("convective") or {},
        "sat_live": nc.get("sat_live") or {},
    }


@router.get("/nowcast/live")
@router.get("/nowcast-live")
async def nowcast_live_api(loc: Location = Depends(loc_from_query)):
    snap = await build_snapshot(loc)
    return _nowcast_live_body(snap)


@router.get("/live-nowcast")
async def nowcast_live_alias(loc: Location = Depends(loc_from_query)):
    """Alias so older proxies that drop a nested /live segment still work."""
    snap = await build_snapshot(loc)
    return _nowcast_live_body(snap)


@router.get("/nowcast/sat")
@router.get("/nowcast-sat")
async def nowcast_sat_api(
    loc: Location = Depends(loc_from_query),
    stride: int = Query(default=60, ge=1, le=60),
):
    """Live Kalman rain-rate between observation scenes. stride=1 or 60."""
    from app.providers import sat_obs
    from app.science import sat_kalman
    from app.science.sat_phys import hydrate

    snap = await build_snapshot(loc)
    nc = (snap.science or {}).get("nowcast") or {}
    src_info = sat_obs.available_source()
    knots = sat_obs.knots_from_nowcast(nc)
    attached = nc.get("sat") or {}
    source = attached.get("source") or src_info["source"]
    kind = attached.get("source_kind") or src_info["source_kind"]
    stride_s = 1 if int(stride) <= 1 else 60
    drivers = hydrate(attached.get("drivers"))
    blob = sat_kalman.pack(
        snap.location,
        knots,
        source=source,
        source_kind=kind,
        stride_s=stride_s,
        compact=False,
        drivers=drivers,
    )
    locked = nc.get("locked") or {}
    blob["rewrites_locked"] = False
    return {
        "location": snap.location.model_dump(),
        "stride_s": stride_s,
        "sat": blob,
        "locked": locked,
        "source_available": src_info,
        "engine": "sat_kalman",
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


@router.get("/alerts")
async def alerts_api(loc: Location = Depends(loc_from_query)):
    """Warnings, actions, and live hazard lists without the full dashboard."""
    snap = await build_snapshot(loc)
    live = snap.live
    return {
        "location": snap.location.model_dump(),
        "generated_at": snap.generated_at,
        "warnings": [w.model_dump() for w in snap.prescriptive.warnings],
        "actions": [a.model_dump() for a in snap.prescriptive.actions],
        "quakes": live.quakes,
        "tsunami": live.tsunami,
        "air": live.air,
        "flood": live.flood,
    }


@router.get("/market")
async def market_api(loc: Location = Depends(loc_from_query)):
    """Agmarknet / OGD mandi slice."""
    snap = await build_snapshot(loc)
    return {
        "location": snap.location.model_dump(),
        "generated_at": snap.generated_at,
        "ogd": snap.ogd,
    }


@router.get("/compare")
async def compare_api(a: str = Query(min_length=2), b: str = Query(min_length=2)):
    return await compare(a, b)


@router.get("/nowcast/storm-map")
@router.get("/nowcast-storm-map")
async def storm_map_api(state: str = Query(min_length=2)):
    from app.science.storm_map import build as build_storm_map

    return await build_storm_map(state)


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
    nc = (snap.science or {}).get("nowcast") or {}
    lock = nc.get("locked") or {}
    sms = (
        f"{snap.location.place_name or snap.location.district}: "
        f"pump {lock.get('p_interrupt_90m', '—')} "
        f"{'HOLD' if (nc.get('pump') or {}).get('action') == 'hold' else 'ok'}; "
        f"field {'closed' if lock.get('enterable_2h') is False else 'open'}; "
        f"onset {str(lock.get('onset') or '—')[11:16]}"
    )
    return {
        "location": snap.location.model_dump(),
        "brief": text,
        "sms": sms[:280],
        "template_id": tid,
        "slots": slots,
        "risks": [r.model_dump() for r in snap.risks],
        "outlook_days": snap.predictive.outlook_days,
        "nowcast": lock,
    }

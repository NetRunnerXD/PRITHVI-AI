from __future__ import annotations

from typing import Any

from app.agents.views import compact_nowcast, compact_science
from app.data.india_districts import search_districts as gaz_search
from app.rag import store as rag
from app.schemas.dashboard import DashboardSnapshot
from app.services.location_svc import list_districts as loc_list, list_states as loc_states, nearby, resolve_location, search
from app.services.location_svc import search_places
from app.tools.registry import Registry, Tool


def build_registry(snap: DashboardSnapshot, extra: dict[str, Any] | None = None) -> Registry:
    extra = extra or {}
    reg = Registry()
    loc = snap.location.model_dump()
    risks = [r.model_dump() for r in snap.risks]
    preds = snap.predictive.model_dump()
    current = snap.descriptive.current.model_dump()
    prescriptions = [p.model_dump() for p in snap.prescriptive.actions]
    warnings = [w.model_dump() for w in snap.prescriptive.warnings]
    veg = snap.vegetation
    series = snap.descriptive.series

    async def get_rain_window(
        place: str | None = None,
        start: str | None = None,
        end: str | None = None,
        **_: Any,
    ) -> dict:
        from datetime import date

        from app.agents.dates import parse_window, today_ist
        from app.services.rain_window import fetch_window

        target = snap.location
        if place:
            target = resolve_location(q=str(place))
        today = today_ist()
        a = b = None
        try:
            if start:
                a = date.fromisoformat(str(start)[:10])
            if end:
                b = date.fromisoformat(str(end)[:10])
        except ValueError:
            a = b = None
        if a is None or b is None:
            from datetime import timedelta

            win = parse_window(f"{start or ''} {end or ''}", today)
            a = a or (win or {}).get("start") or today
            b = b or (win or {}).get("end") or (a + timedelta(days=6))
        return await fetch_window(target, a, b)

    async def get_weather_forecast(
        days: int = 7,
        start: str | None = None,
        end: str | None = None,
        place: str | None = None,
        **_: Any,
    ) -> dict:
        if start or end or place:
            return await get_rain_window(place=place, start=start, end=end)
        n = max(1, min(int(days or 7), 16))
        outlook = preds.get("outlook_days") or []
        return {
            "location": loc,
            "precip_next_3d_mm": preds.get("precip_next_3d_mm"),
            "precip_7d_mm": preds.get("precip_7d_mm"),
            "precip_probability_pct": (preds.get("precip_probability_pct") or [])[:n],
            "temp_max_c": (preds.get("temp_max_c") or [])[:n],
            "temp_min_c": (preds.get("temp_min_c") or [])[:n],
            "days": outlook[:n],
            "current": current,
            "model": preds.get("model"),
            "note": "Snapshot outlook (Open-Meteo daily). For a named date range call get_rain_window.",
            "widget": "predictive",
        }

    async def get_soil_moisture(**_: Any) -> dict:
        return {
            "soil_moisture_m3m3": current.get("soil_moisture_m3m3"),
            "et0_mm": current.get("et0_mm"),
            "unit": "m3/m3",
            "depth": "0-7cm",
            "source": "open-meteo",
            "widget": "descriptive",
        }

    async def get_imd_warnings(**_: Any) -> dict:
        return {
            "warnings": warnings,
            "source": "imd-cap + multi-hazard",
            "imd_rest": snap.provider_status.get("imd-rest"),
            "provider_status": {
                "imd_cap": snap.provider_status.get("imd-cap"),
                "imd_rest": snap.provider_status.get("imd-rest"),
                "incois": snap.provider_status.get("incois-tsunami"),
                "usgs": snap.provider_status.get("usgs-seismic"),
                "open_meteo_flood": snap.provider_status.get("open-meteo-flood"),
                "open_meteo_marine": snap.provider_status.get("open-meteo-marine"),
                "cpcb": snap.provider_status.get("data.gov.in-aqi"),
            },
            "note": "Multi-hazard watch. Open-Meteo has weather/flood/marine/air, not seismic or tsunami.",
            "widget": "warnings",
        }

    async def get_hazard_watch(**_: Any) -> dict:
        live = snap.live.model_dump() if getattr(snap, "live", None) else {}
        return {
            "warnings": warnings,
            "live": live,
            "current": current,
            "provider_status": snap.provider_status,
            "note": "Open-Meteo: weather, flood, marine, air. Seismic: USGS. Tsunami: INCOIS ITEWS. Air also CPCB.",
            "widget": "warnings",
        }

    async def get_flood_outlook(**_: Any) -> dict:
        flood = next((r for r in risks if r["id"] == "flood"), None)
        return {
            "discharge_trend": preds.get("flood_discharge_trend"),
            "river_discharge": preds.get("river_discharge"),
            "flood_watch_dates": preds.get("flood_watch_dates"),
            "flood_risk": flood,
            "widget": "risks",
        }

    async def get_vegetation_index(**_: Any) -> dict:
        return {**veg, "widget": "vegetation"}

    async def get_air_quality(place: str | None = None, **_: Any) -> dict:
        from app.providers import datagov
        from app.services.location_svc import resolve_location

        target = snap.location
        if place:
            target = resolve_location(q=str(place))
        aqi, st = await datagov.nearest_aqi(
            target.lat, target.lon, target.state, target.district, place=place or target.district
        )
        return {
            "cpcb": aqi,
            "queried": place or target.district,
            "resolved": target.model_dump(),
            "provider_status": st,
            "source": "data.gov.in / CPCB",
            "widget": "descriptive",
        }

    async def get_mandi_prices(**_: Any) -> dict:
        return {
            "mandi": (snap.ogd or {}).get("mandi") or [],
            "unit": "INR/quintal",
            "provider_status": snap.provider_status.get("data.gov.in-mandi"),
            "source": "data.gov.in / Agmarknet",
            "widget": "mandi",
        }

    async def get_risk_scores(risk_id: str | None = None, **_: Any) -> dict:
        cards = risks
        if risk_id:
            cards = [r for r in risks if r["id"] == risk_id] or risks
        return {"risks": cards, "widget": "risks"}

    async def get_prescriptions(crop: str | None = None, **_: Any) -> dict:
        return {"actions": prescriptions, "crop": crop or loc.get("crop_hint"), "widget": "prescriptive"}

    async def retrieve_playbook(topic: str = "irrigation", locale: str = "en", **_: Any) -> dict:
        return rag.retrieve(topic, locale)

    async def search_aikosh(query: str = "agriculture", **_: Any) -> dict:
        return {
            "status": snap.provider_status.get("aikosh"),
            "query": query,
            "note": "Set AIKOSH_API_KEY to search Kisan Call Centre and agro-climatic datasets.",
        }

    async def get_dual_predictions(**_: Any) -> dict:
        return {"predictions": snap.predictions, "widget": "predicted"}

    async def get_7day_outlook(place: str | None = None, **_: Any) -> dict:
        src_preds = preds
        if place:
            from app.services.snapshot import build_snapshot

            other = await build_snapshot(resolve_location(q=str(place)))
            src_preds = other.predictive.model_dump()
        return {
            "outlook_days": src_preds.get("outlook_days") or [],
            "precip_7d_mm": src_preds.get("precip_7d_mm"),
            "et0_7d_mm": src_preds.get("et0_7d_mm"),
            "water_balance_7d_mm": src_preds.get("water_balance_7d_mm"),
            "irrigate_dates": src_preds.get("irrigate_dates") or [],
            "flood_watch_dates": src_preds.get("flood_watch_dates") or [],
            "widget": "predictive",
        }

    async def get_water_balance(**_: Any) -> dict:
        wb = (snap.science or {}).get("water_balance") or {}
        return {
            "plot_m2": loc.get("plot_m2") or 400,
            "precip_7d_mm": preds.get("precip_7d_mm"),
            "et0_7d_mm": preds.get("et0_7d_mm"),
            "water_balance_7d_mm": preds.get("water_balance_7d_mm"),
            "soil_m3m3": current.get("soil_moisture_m3m3"),
            "identity": wb,
            "method": wb.get("method") or "precip - ET0 over 7 days",
            "widget": "predictive",
        }

    async def get_science_pack(place: str | None = None, **_: Any) -> dict:
        src = snap
        if place:
            from app.services.snapshot import build_snapshot

            src = await build_snapshot(resolve_location(q=str(place)))
        return {"science": compact_science(src.science or {}), "widget": "science"}

    async def get_nowcast(speech: str | None = None, place: str | None = None, **_: Any) -> dict:
        from app.science.nowcast import apply_speech_only

        src = snap
        if place:
            from app.services.snapshot import build_snapshot

            src = await build_snapshot(resolve_location(q=str(place)))
        nc = (src.science or {}).get("nowcast") or {}
        if speech and nc.get("hours"):
            nc = apply_speech_only(nc, str(speech))
        out = compact_nowcast(nc)
        out["queried"] = place or (src.location.place_name or src.location.district)
        return out

    async def get_hourly_series(variable: str = "precip", **_: Any) -> dict:
        key = {
            "precip": "precip_hourly",
            "temp": "temp_hourly",
            "soil": "soil_hourly",
            "rh": "rh_hourly",
            "wind": "wind_hourly",
            "wind_dir": "wind_dir_hourly",
            "cloud": "cloud_hourly",
            "aqi": "aqi_hourly",
            "aqi_history": "aqi_history",
            "wave": "wave_hourly",
        }.get(variable, "precip_hourly")
        pts = [p.model_dump() if hasattr(p, "model_dump") else p for p in (series.get(key) or [])[:48]]
        return {"variable": variable, "series": pts, "widget": "descriptive"}

    async def explain_risk(risk_id: str = "flood", **_: Any) -> dict:
        card = next((r for r in risks if r["id"] == risk_id), None)
        return {"risk": card, "widget": "risks"}

    async def get_nearby_districts(limit: int = 6, **_: Any) -> dict:
        found = [n.model_dump() for n in nearby(snap.location.lat, snap.location.lon, limit=int(limit or 6))]
        return {"nearby": found, "widget": "map"}

    async def search_districts(query: str, **_: Any) -> dict:
        return {"results": [x.model_dump() for x in search(str(query or ""), limit=6)]}

    async def compare_districts(other: str | None = None, **_: Any) -> dict:
        name = str(other or "").strip()
        if not name:
            return {
                "error": "need_other_place",
                "ask": "Which second Indian town or district should I compare?",
            }
        from app.services.compare import compare

        payload = await compare(snap.location.district, name, loc_a=snap.location)
        return {**payload, "widget": "compare"}

    async def geo_search(query: str, **_: Any) -> dict:
        found = await search_places(str(query or ""), limit=6)
        return {"results": [x.model_dump() for x in found], "widget": "map"}

    async def capability(metric: str = "", **_: Any) -> dict:
        holes = {
            "radar": "No radar ingest. Nowcast is a 0–6 h decision object on Open-Meteo hours.",
            "insat": "INSAT-3D HEM HDF needs a cached MOSDAC file. Live nowcast uses IMD public INSAT IR JPEG + NASA GIBS IMERG unless HEM is ready.",
            "lightning": "Live strokes from Weatherbit when WEATHERBIT_API_KEY is set.",
            "ncs": "NCS has no public JSON. Seismic is USGS FDSN.",
            "imd_rest": "api.imd.gov.in returns 401 without IP whitelist. Official warnings are IMD CAP RSS.",
            "gauge": "Open-Meteo daily/hourly is a model, not a rain-gauge.",
        }
        key = (metric or "").strip().lower()
        if key == "lightning":
            from app.config import get_settings

            on = bool(get_settings().weatherbit_api_key)
            return {"available": on, "metric": key, "reason": holes["lightning"], "source": "weatherbit"}
        if key in holes:
            return {"available": False, "metric": key, "reason": holes[key]}
        return {
            "available": True,
            "metric": key or "catalog",
            "unavailable": holes,
            "note": "Ask capability with metric=radar|insat|ncs|imd_rest|gauge for a hole.",
        }

    async def present_answer(
        format: str = "free",
        title: str | None = None,
        blocks: list | None = None,
        sources: list | None = None,
        **_: Any,
    ) -> dict:
        return {
            "ok": True,
            "spec": {
                "format": format,
                "title": title,
                "blocks": blocks or [],
                "sources": sources or [],
            },
        }

    async def list_states(**_: Any) -> dict:
        return {"states": loc_states(), "count": len(loc_states())}

    async def list_districts(state: str | None = None, **_: Any) -> dict:
        rows = loc_list(state)
        return {
            "state": state or "India (gazetteer)",
            "count": len(rows),
            "districts": [r.model_dump() for r in rows],
        }

    async def rank_districts(state: str | None = None, metric: str = "flood", limit: int = 25, **_: Any) -> dict:
        from app.services.scan import rank_districts as scan_rank

        payload = await scan_rank(state, metric=metric or "flood", limit=int(limit or 25))
        return {**payload, "widget": "rank"}

    async def predict_district(name: str, **_: Any) -> dict:
        from app.services.scan import predict_one

        hits = gaz_search(str(name or ""), limit=1)
        if not hits:
            return {"error": f"unknown district {name}"}
        return await predict_one(hits[0])

    async def get_state_mandi(state: str | None = None, **_: Any) -> dict:
        from app.providers import datagov

        st = state or loc.get("state")
        grouped, status = await datagov.mandi_by_state(st)
        return {
            "state": st,
            "status": status,
            "districts": grouped,
            "district_count": len(grouped),
            "source": "data.gov.in / Agmarknet",
            "widget": "mandi",
        }

    async def switch_location(name: str, **_: Any) -> dict:
        from app.services.snapshot import build_snapshot

        new_loc = resolve_location(q=str(name or ""))
        new_snap = await build_snapshot(new_loc)
        extra["snap"] = new_snap
        return {
            "location": new_loc.model_dump(),
            "dashboard": new_snap.model_dump(),
            "widget": "dashboard",
        }

    specs = [
        Tool(
            "get_rain_window",
            "Daily rainfall (mm) for a place and calendar date range. "
            "Pass start and end as YYYY-MM-DD (e.g. 2026-08-23 to 2026-08-28) and optional place (Haldia). "
            "Quote only the returned days. Open-Meteo model, not a gauge. Horizon about 16 days.",
            {
                "type": "object",
                "properties": {
                    "place": {"type": "string"},
                    "start": {"type": "string", "description": "YYYY-MM-DD"},
                    "end": {"type": "string", "description": "YYYY-MM-DD"},
                },
                "additionalProperties": True,
            },
            get_rain_window,
            "window",
        ),
        Tool("get_weather_forecast", "Quantitative forecast. Prefer get_rain_window for named dates. Optional days, start, end, place.",
             {
                 "type": "object",
                 "properties": {
                     "days": {"type": "integer"},
                     "start": {"type": "string"},
                     "end": {"type": "string"},
                     "place": {"type": "string"},
                 },
                 "additionalProperties": True,
             },
             get_weather_forecast, "predictive"),
        Tool("get_dual_predictions", "Trusted Open-Meteo vs hybrid AI–NWP Vincentize blend (q50 rain, model weights, IMD heavy-rain probability).",
             {"type": "object", "properties": {}},
             get_dual_predictions, "predicted"),
        Tool("get_7day_outlook", "Day-by-day 7-day outlook with irrigate/flood flags and soil bucket. Optional place.",
             {"type": "object", "properties": {"place": {"type": "string"}}, "additionalProperties": True},
             get_7day_outlook, "predictive"),
        Tool("get_water_balance", "7-day plot water balance (precip minus ET0) plus identified P−ET−runoff−ΔS identity.",
             {"type": "object", "properties": {}, "additionalProperties": True},
             get_water_balance, "predictive"),
        Tool("get_science_pack", "Hysteresis, regret, phenology, monsoon, CWC, vernacular. Compact — no Kalman/gap. Optional place.",
             {"type": "object", "properties": {"place": {"type": "string"}}},
             get_science_pack, "science"),
        Tool(
            "get_nowcast",
            "Locked 0–6 h nowcast for this pin or optional place. Quote only locked fields. Optional speech=user text (category only, never millimetres). Never sat/gap/playhead.",
            {
                "type": "object",
                "properties": {"speech": {"type": "string"}, "place": {"type": "string"}},
                "additionalProperties": True,
            },
            get_nowcast,
            "nowcast",
        ),
        Tool("get_hourly_series", "Hourly series: precip|temp|soil|rh|wind.",
             {"type": "object", "properties": {"variable": {"type": "string"}}, "additionalProperties": True},
             get_hourly_series, "descriptive"),
        Tool("get_soil_moisture", "Live 0–7 cm soil moisture and ET0.",
             {"type": "object", "properties": {}, "additionalProperties": True},
             get_soil_moisture, "descriptive"),
        Tool("get_imd_warnings", "Official IMD CAP plus multi-hazard watches (flood, air, marine, seismic, tsunami).",
             {"type": "object", "properties": {}, "additionalProperties": True},
             get_imd_warnings, "warnings"),
        Tool("get_hazard_watch", "Live multi-hazard board: sky, wind, flood, marine, CPCB/Open-Meteo air, USGS quakes, INCOIS tsunami.",
             {"type": "object", "properties": {}, "additionalProperties": True},
             get_hazard_watch, "warnings"),
        Tool("get_flood_outlook", "River discharge trend and flood risk card.",
             {"type": "object", "properties": {}, "additionalProperties": True},
             get_flood_outlook, "risks"),
        Tool("get_vegetation_index", "Modelled vegetation stress (not NDVI).",
             {"type": "object", "properties": {}, "additionalProperties": True},
             get_vegetation_index, "vegetation"),
        Tool("get_air_quality", "CPCB National AQI for the nearest station.",
             {"type": "object", "properties": {}, "additionalProperties": True},
             get_air_quality),
        Tool("get_mandi_prices", "Today's Agmarknet mandi modal prices (INR/quintal).",
             {"type": "object", "properties": {}, "additionalProperties": True},
             get_mandi_prices, "mandi"),
        Tool("get_risk_scores", "XAI risk cards. Optional risk_id: flood|drought|heat|irrigation_need|air_quality.",
             {"type": "object", "properties": {"risk_id": {"type": "string"}}, "additionalProperties": True},
             get_risk_scores, "risks"),
        Tool("explain_risk", "Breakdown of one risk card (factors + confidence).",
             {"type": "object", "properties": {"risk_id": {"type": "string"}}, "additionalProperties": True},
             explain_risk, "risks"),
        Tool("get_prescriptions", "Prescribed actions and liter estimates from the rule engine.",
             {"type": "object", "properties": {"crop": {"type": "string"}}, "additionalProperties": True},
             get_prescriptions, "prescriptive"),
        Tool("retrieve_playbook", "Bundled crop / irrigation playbook (RAG).",
             {"type": "object", "properties": {"topic": {"type": "string"}, "locale": {"type": "string"}}},
             retrieve_playbook),
        Tool("search_aikosh", "Search AIKosh datasets (requires API key).",
             {"type": "object", "properties": {"query": {"type": "string"}}},
             search_aikosh),
        Tool("get_nearby_districts", "Nearest gazetteer districts for the map.",
             {"type": "object", "properties": {"limit": {"type": "integer"}}},
             get_nearby_districts, "map"),
        Tool("search_districts", "Search Indian districts by name.",
             {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]},
             search_districts),
        Tool("compare_districts", "Compare this focus place with another Indian town or district (other=name). Ask if other is missing.",
             {"type": "object", "properties": {"other": {"type": "string"}}},
             compare_districts, "compare"),
        Tool("geo_search", "Search Indian towns and districts (gazetteer + Open-Meteo India).",
             {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]},
             geo_search, "map"),
        Tool(
            "capability",
            "What Rituchakra cannot provide (radar, INSAT, NCS, IMD REST, rain-gauge). Call before inventing a missing metric.",
            {"type": "object", "properties": {"metric": {"type": "string"}}},
            capability,
        ),
        Tool(
            "present_answer",
            "Submit the final answer layout. Numbers only as cite: paths or table from= tool arrays. Then stop.",
            {
                "type": "object",
                "properties": {
                    "format": {"type": "string"},
                    "title": {"type": "string"},
                    "blocks": {"type": "array"},
                    "sources": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["blocks"],
            },
            present_answer,
        ),
        Tool("list_states", "List Indian states/UTs in the gazetteer.",
             {"type": "object", "properties": {}},
             list_states),
        Tool("list_districts", "List districts (and HQ coords) for a state, or all gazetteer districts if state omitted.",
             {"type": "object", "properties": {"state": {"type": "string"}}},
             list_districts),
        Tool("rank_districts", "Live-rank districts in a state by flood|rain|drought|heat|irrigation using Open-Meteo + local ML.",
             {"type": "object", "properties": {
                 "state": {"type": "string"},
                 "metric": {"type": "string"},
                 "limit": {"type": "integer"},
             }},
             rank_districts, "rank"),
        Tool("predict_district", "3-day rain/soil/flood-score for one named district.",
             {"type": "object", "properties": {"name": {"type": "string"}}, "required": ["name"]},
             predict_district),
        Tool("get_state_mandi", "Today's Agmarknet arrivals grouped by district for a state.",
             {"type": "object", "properties": {"state": {"type": "string"}}},
             get_state_mandi, "mandi"),
        Tool("switch_location", "Move the dashboard focus to another Indian district by name.",
             {"type": "object", "properties": {"name": {"type": "string"}}, "required": ["name"]},
             switch_location, "dashboard"),
    ]
    for t in specs:
        reg.register(t)
    return reg

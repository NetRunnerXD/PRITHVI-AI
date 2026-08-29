"""One opt-in data library. Nothing runs until the model calls data()."""

from __future__ import annotations

import re
from datetime import date
from typing import Any

from app.agents.dates import parse_window, today_ist
from app.agents.views import compact_nowcast, strip_forbidden
from app.schemas.location import Location
from app.services.location_svc import resolve_india_place, search_places

NEEDS = (
    "nowcast",
    "rain_window",
    "forecast",
    "aqi",
    "quality",
    "mandi",
    "warnings",
    "compare",
    "rank",
    "states_weather",
    "risks",
    "place_search",
    "capability",
)

SCHEMA = {
    "type": "function",
    "function": {
        "name": "data",
        "description": (
            "Fetch one Rituchakra fact pack. Call only when the user needs a real number. "
            "Do not call for chit-chat or off-topic questions."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "need": {
                    "type": "string",
                    "enum": list(NEEDS),
                    "description": "Which fact pack to load",
                },
                "place": {"type": "string", "description": "Indian town or district"},
                "start": {"type": "string", "description": "YYYY-MM-DD"},
                "end": {"type": "string", "description": "YYYY-MM-DD"},
                "other": {"type": "string", "description": "Second place for compare"},
                "state": {"type": "string", "description": "Indian state for rank"},
                "metric": {"type": "string", "description": "rank metric: flood|rain|drought|heat|irrigation"},
                "question": {"type": "string"},
            },
            "required": ["need"],
        },
    },
}

HOLES = {
    "radar": "No radar ingest. Nowcast is a 0–6 h decision object on Open-Meteo hours.",
    "insat": "INSAT-3D HEM HDF needs a cached MOSDAC file. Live nowcast uses IMD public INSAT IR JPEG + NASA GIBS IMERG unless HEM is ready.",
    "lightning": "Live strokes from Weatherbit when WEATHERBIT_API_KEY is set.",
    "ncs": "NCS has no public JSON. Seismic is USGS FDSN.",
    "imd_rest": "api.imd.gov.in returns 401. Official warnings are IMD CAP RSS.",
    "gauge": "Open-Meteo daily/hourly is a model, not a rain-gauge.",
}


def parse_text_call(text: str) -> dict[str, Any] | None:
    """If Ollama dropped tools, accept a single line: data: rain_window start=2026-08-23 end=2026-08-28 place=Haldia"""
    raw = (text or "").strip()
    m = re.search(r"\bdata\s*:?\s*([a-z_]+)\b(.*)$", raw, re.I | re.M)
    if not m:
        return None
    need = m.group(1).lower()
    if need not in NEEDS:
        return None
    args: dict[str, Any] = {"need": need}
    for km in re.finditer(r"\b(place|start|end|other|metric|question)=(\S+)", m.group(2) or ""):
        args[km.group(1)] = km.group(2).strip("\"',")
    return args


class DataLib:
    def __init__(self, loc: Location, speech: str = ""):
        self.loc = loc
        self.speech = speech
        self.snap: Any = None
        self._snaps: dict[tuple[float, float], Any] = {}

    def _snap_key(self, loc: Location) -> tuple[float, float]:
        return (round(float(loc.lat), 4), round(float(loc.lon), 4))

    async def _snap(self, loc: Location | None = None):
        target = loc or self.loc
        key = self._snap_key(target)
        cached = self._snaps.get(key)
        if cached is not None:
            self.snap = cached
            return cached
        from app.services.snapshot import build_snapshot

        snap = await build_snapshot(target)
        self._snaps[key] = snap
        self.snap = snap
        if loc is None:
            self.loc = snap.location
        return snap

    async def _place(self, place: str | None) -> Location | None:
        if place:
            return await resolve_india_place(str(place))
        return self.loc

    async def call(self, args: dict[str, Any]) -> dict[str, Any]:
        need = str(args.get("need") or "").strip().lower()
        if need not in NEEDS:
            return {"error": f"unknown need {need}", "available": NEEDS}
        place = args.get("place")
        loc = await self._place(place if isinstance(place, str) else None)
        if place and loc is None:
            return {"need": need, "error": "unknown_place", "place": place}
        if loc is None:
            return {"need": need, "error": "no_location"}
        if place:
            self.loc = loc
        if need == "capability":
            q = str(args.get("question") or args.get("metric") or "").lower()
            if q in HOLES:
                return {"need": need, "available": False, "metric": q, "reason": HOLES[q]}
            return {"need": need, "available": True, "unavailable": HOLES}
        if need == "place_search":
            q = str(place or args.get("question") or "")
            found = await search_places(q, limit=6)
            return {"need": need, "results": [x.model_dump() for x in found]}
        if need == "rain_window":
            return await self._rain_window(loc, args)
        if need == "nowcast":
            snap = await self._snap(loc if place else None)
            nc = (snap.science or {}).get("nowcast") or {}
            if self.speech and nc.get("hours"):
                from app.science.nowcast import apply_speech_only

                nc = apply_speech_only(nc, self.speech)
            out = compact_nowcast(nc)
            out["need"] = "nowcast"
            out["place"] = loc.place_name or loc.district
            return out
        if need == "forecast":
            snap = await self._snap(loc if place else None)
            p = snap.predictive.model_dump()
            cur = snap.descriptive.current
            return strip_forbidden(
                {
                    "need": "forecast",
                    "place": loc.place_name or loc.district,
                    "label": loc.label,
                    "temp_c": cur.temp_c,
                    "precip_1h_mm": cur.precip_1h_mm,
                    "sky_label": cur.sky_label,
                    "precip_next_3d_mm": p.get("precip_next_3d_mm"),
                    "precip_7d_mm": p.get("precip_7d_mm"),
                    "water_balance_7d_mm": p.get("water_balance_7d_mm"),
                    "outlook_days": (p.get("outlook_days") or [])[:7],
                }
            )
        if need == "aqi":
            from app.providers import datagov

            qplace = loc.place_name or loc.district
            aqi, st = await datagov.nearest_aqi(loc.lat, loc.lon, loc.state, loc.district, place=qplace)
            om = None
            if not aqi or st != "ok" or aqi.get("value") is None:
                snap = await self._snap(loc if place else None)
                cur = snap.descriptive.current
                om = cur.om_us_aqi
            return {
                "need": "aqi",
                "cpcb": aqi if st == "ok" else None,
                "om_us_aqi": om,
                "provider_status": st,
                "place": qplace,
                "available": bool(st == "ok" and aqi and aqi.get("value") is not None) or om is not None,
                "note": None if st == "ok" else st,
            }
        if need == "quality":
            snap = await self._snap(loc if place else None)
            q = snap.quality or {}
            air = q.get("air") or {}
            return strip_forbidden(
                {
                    "need": "quality",
                    "place": loc.place_name or loc.district,
                    "air": air,
                    "climate": q.get("climate"),
                    "moon": q.get("moon"),
                    "marine": q.get("marine"),
                    "seismic": (q.get("seismic") or [])[:5],
                    "gdacs": q.get("gdacs") or [],
                    "mosdac": q.get("mosdac") or {},
                }
            )
        if need == "mandi":
            snap = await self._snap(loc if place else None)
            return {
                "need": "mandi",
                "mandi": (snap.ogd or {}).get("mandi") or [],
                "unit": "INR/quintal",
                "place": loc.district,
            }
        if need == "warnings":
            snap = await self._snap(loc if place else None)
            warns = [w.model_dump() for w in snap.prescriptive.warnings[:8]]
            return {"need": "warnings", "warnings": warns, "provider_status": snap.provider_status}
        if need == "compare":
            other = str(args.get("other") or "").strip()
            if not other:
                return {"need": "compare", "error": "need_other_place", "ask": "Which second Indian town or district?"}
            from app.services.compare import compare

            payload = await compare(loc.district, other, loc_a=loc)
            payload["need"] = "compare"
            return strip_forbidden(payload)
        if need == "rank":
            from app.data.india_districts import match_state
            from app.services.scan import rank_districts as scan_rank

            metric = str(args.get("metric") or "flood")
            state = str(args.get("state") or "").strip() or match_state(str(args.get("question") or "")) or loc.state
            payload = await scan_rank(state, metric=metric, limit=25)
            payload["need"] = "rank"
            return {
                "need": "rank",
                "state": payload.get("state"),
                "metric": payload.get("metric"),
                "method": payload.get("method"),
                "ranked": (payload.get("ranked") or [])[:20],
                "note": payload.get("note"),
            }
        if need == "states_weather":
            from app.services.scan import rank_states

            metric = str(args.get("metric") or "flood")
            payload = await rank_states(metric=metric, limit=int(args.get("limit") or 16))
            return payload
        if need == "risks":
            snap = await self._snap(loc if place else None)
            cards = [
                {"id": r.id, "label": r.label, "score_pct": r.score_pct, "severity": r.severity}
                for r in snap.risks
            ]
            return {"need": "risks", "place": loc.place_name or loc.district, "risks": cards}
        return {"error": f"unhandled {need}"}

    async def _rain_window(self, loc: Location, args: dict[str, Any]) -> dict[str, Any]:
        from app.services.rain_window import fetch_window

        today = today_ist()
        a = b = None
        try:
            if args.get("start"):
                a = date.fromisoformat(str(args["start"])[:10])
            if args.get("end"):
                b = date.fromisoformat(str(args["end"])[:10])
        except ValueError:
            a = b = None
        if a is None or b is None:
            win = parse_window(f"{args.get('start') or ''} {args.get('end') or ''}", today)
            if not win:
                win = parse_window(str(args.get("question") or ""), today)
            a = a or (win or {}).get("start") or today
            b = b or (win or {}).get("end") or a
        pack = await fetch_window(loc, a, b)
        pack["need"] = "rain_window"
        return pack


def suggestions_for(collected: dict[str, Any], loc: Location) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    pin = {
        "location": loc.model_dump(),
        "center": [loc.lat, loc.lon],
        "zoom": 10,
    }
    name = loc.place_name or loc.district
    if "nowcast" in collected:
        out.append({"id": "open-nowcast", "label": f"Open the 0–6 hour nowcast for {name}", "tab": "nowcast", **pin})
    win = collected.get("rain_window")
    if isinstance(win, dict) and (win.get("days") or win.get("missing")):
        out.append(
            {
                "id": "open-forecast",
                "label": f"Show this date window on Forecast for {name}",
                "tab": "forecast",
                "window": win,
                **pin,
            }
        )
    if "forecast" in collected and not any(s["id"] == "open-forecast" for s in out):
        out.append({"id": "open-forecast", "label": f"Open the 7-day forecast for {name}", "tab": "forecast", **pin})
    if "aqi" in collected or "warnings" in collected:
        out.append({"id": "open-alerts", "label": f"Open alerts for {name}", "tab": "alerts", **pin})
    if "mandi" in collected:
        out.append({"id": "open-market", "label": f"Open mandi prices for {name}", "tab": "market", **pin})
    if "risks" in collected:
        out.append({"id": "open-risks", "label": f"Open risk cards for {name}", "tab": "risks", **pin})
    if "compare" in collected or "rank" in collected or "states_weather" in collected:
        out.append({"id": "open-forecast-rank", "label": "Open the forecast board", "tab": "forecast", **pin})
    if "place_search" in collected or any(k in collected for k in ("nowcast", "rain_window", "forecast", "aqi", "risks")):
        out.append({"id": "focus-map", "label": f"Focus the map on {name}", "tab": "map", **pin})
    # de-dupe by id
    seen: set[str] = set()
    uniq = []
    for s in out:
        if s["id"] in seen:
            continue
        seen.add(s["id"])
        uniq.append(s)
    return uniq


def attachments_for(collected: dict[str, Any]) -> list[dict[str, Any]]:
    blocks: list[dict[str, Any]] = []
    win = collected.get("rain_window") or {}
    if isinstance(win, dict) and win.get("days"):
        rows = [
            {k: r.get(k) for k in ("date", "precip_mm", "precip_prob_pct", "temp_max_c") if k in r}
            for r in win["days"]
            if isinstance(r, dict)
        ]
        blocks.append({"type": "table", "from": "rain_window.days", "columns": list(rows[0].keys()) if rows else [], "rows": rows})
    nc = collected.get("nowcast") or {}
    locked = nc.get("nowcast") if isinstance(nc, dict) else {}
    if isinstance(locked, dict) and locked:
        items = []
        for label, key in (
            ("90 min interrupt", "p_interrupt_90m"),
            ("Onset", "onset"),
            ("Field 2h", "enterable_2h"),
        ):
            if locked.get(key) is not None:
                items.append({"label": label, "value": locked.get(key), "cite": f"nowcast.{key}"})
        pump = nc.get("pump") or {}
        if pump.get("p_interrupt_90m") is not None and not any(i["cite"] == "nowcast.p_interrupt_90m" for i in items):
            items.append({"label": "90 min interrupt", "value": pump.get("p_interrupt_90m"), "cite": "nowcast.p_interrupt_90m"})
        if items:
            blocks.append({"type": "metrics", "items": items})
    return blocks

from __future__ import annotations

from typing import Any

from app import cache
from app.i18n.templates import render
from app.schemas.dashboard import DashboardSnapshot
from app.schemas.location import Location
from app.services.snapshot_obs import gather_observations, _blank_obs
from app.services.snapshot_live import (
    _build_live,
    _quake_display,
    _vera_pack,
    _vegetation,
    _vis_km,
)
from app.services.snapshot_assemble import (
    _assemble_snapshot,
    _finalize_quality,
    _low_elev,
    _n,
    _series,
    _warnings,
)

# Tests and callers import these from this module.

def pin_key(loc: Location) -> str:
    la = round(round(float(loc.lat) / 0.05) * 0.05, 2)
    lo = round(round(float(loc.lon) / 0.05) * 0.05, 2)
    return f"snap8:{la}:{lo}"


def peek_snapshot(loc: Location) -> DashboardSnapshot | None:
    hit = cache.peek(pin_key(loc))
    return hit if isinstance(hit, DashboardSnapshot) else None


async def build_snapshot(
    loc: Location,
    locale: str = "en",
    *,
    full: bool | None = None,
    disabled: set[str] | None = None,
) -> DashboardSnapshot:
    """Always wait for the complete snapshot (all providers) before returning."""
    key = pin_key(loc)
    if disabled:
        # Avoid caching customized disabled profiles in the global pin key
        key = f"{key}:dis:{'_'.join(sorted(disabled))}"
    from app.config import get_settings

    s = get_settings()
    ttl = float(s.snapshot_ttl_s or 600)
    swr = float(s.snapshot_swr_s or 3600)

    async def factory() -> DashboardSnapshot:
        snap = await _assemble_snapshot(loc, locale, enrich=True, disabled=disabled)
        snap.enriching = False
        return snap

    return await cache.aget(key, factory, ttl_s=ttl, swr_s=swr)


async def refresh_recent_snapshots(limit: int = 8) -> int:
    """Rebuild cached pins so OM is hit on a timer, not per browser poll."""
    from app.config import get_settings
    from app.services.location_svc import resolve_location

    keys = cache.keys_prefix("snap8:")
    pins: list[tuple[float, float]] = []
    for k in keys:
        parts = str(k).split(":")
        if len(parts) >= 3:
            try:
                pins.append((float(parts[1]), float(parts[2])))
            except ValueError:
                continue
    s = get_settings()
    if not pins:
        pins.append((float(s.default_lat), float(s.default_lon)))
    n = 0
    ttl = float(s.snapshot_ttl_s or 600)
    swr = float(s.snapshot_swr_s or 3600)
    for lat, lon in pins[:limit]:
        loc = resolve_location(lat=lat, lon=lon)
        snap = await _assemble_snapshot(loc, enrich=True)
        snap.enriching = False
        cache.set(pin_key(loc), snap, ttl, swr)
        n += 1
    return n

def snapshot_tool_views(snap: DashboardSnapshot) -> dict[str, Any]:
    """Start-of-turn index for the Advisor. Locked nowcast only; no Kalman/gap."""
    from app.agents.views import snapshot_index

    return snapshot_index(snap)


def primary_reply(snap: DashboardSnapshot, locale: str, intent: str) -> tuple[str, str, dict]:
    actions = snap.prescriptive.actions
    pump = next((a for a in actions if a.template_id == "nowcast_pump_hold"), None)
    hold = next((a for a in actions if a.template_id == "irrigation_hold_rain"), None)
    apply = next((a for a in actions if a.template_id == "irrigation_apply"), None)
    flood = next((a for a in actions if a.template_id == "flood_prep"), None)
    if intent in {"irrigation", "rain"} and pump:
        text = render(pump.template_id or "", locale, pump.slots)
        return text, pump.template_id or "", pump.slots
    if intent in {"irrigation", "rain", "general"} and hold:
        text = render(hold.template_id or "", locale, hold.slots)
        return text, hold.template_id or "", hold.slots
    if intent == "irrigation" and apply:
        text = render(apply.template_id or "", locale, apply.slots)
        return text, apply.template_id or "", apply.slots
    if intent == "flood" and flood:
        text = render(flood.template_id or "", locale, flood.slots)
        return text, flood.template_id or "", flood.slots
    aqi_act = next((a for a in actions if a.template_id == "aqi_protect"), None)
    if intent == "aqi" and snap.descriptive.current.aqi is not None:
        slots = {
            "aqi": snap.descriptive.current.aqi,
            "category": snap.descriptive.current.aqi_category or "",
            "pollutant": snap.descriptive.current.aqi_pollutant or "",
        }
        if aqi_act:
            return render("aqi_protect", locale, aqi_act.slots), "aqi_protect", aqi_act.slots
        body = f"CPCB National AQI is {slots['aqi']} ({slots['category']}) at {snap.descriptive.current.aqi_station}."
        return render("generic_grounded", locale, {"body": body}), "generic_grounded", slots
    if intent == "price":
        mandi = (snap.ogd or {}).get("mandi") or []
        staples = ("rice", "paddy", "wheat", "potato", "onion", "jute", "mustard")
        def _rank(row: dict) -> tuple:
            name = (row.get("commodity") or "").lower()
            pref = next((i for i, s in enumerate(staples) if s in name), 99)
            return (pref, -(row.get("modal_price") or 0))
        ordered = sorted(mandi, key=_rank)
        bits = [
            f"{r.get('commodity')} {int(r.get('modal_price'))} INR/qtl ({r.get('market')})"
            for r in ordered[:5]
            if r.get("modal_price") is not None
        ]
        summary = "; ".join(bits) if bits else "no mandi arrivals reported for this district today"
        return render("mandi_summary", locale, {"summary": summary}), "mandi_summary", {"summary": summary}
    p = snap.predictive
    soil = snap.descriptive.current.soil_moisture_m3m3
    slots = {
        "rain_mm": p.precip_next_3d_mm,
        "prob": max(p.precip_probability_pct) if p.precip_probability_pct else 0,
        "tmax": ", ".join(f"{t}°C" for t in p.temp_max_c[:3]) or "n/a",
        "soil": f"{soil:.2f} m³/m³" if soil is not None else "n/a",
    }
    extra = ""
    if hold:
        extra = " " + render(hold.template_id or "", locale, hold.slots)
    if flood and intent != "irrigation":
        extra += " " + render(flood.template_id or "", locale, flood.slots)
    return render("forecast_summary", locale, slots) + extra, "forecast_summary", slots

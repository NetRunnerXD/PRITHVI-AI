from __future__ import annotations

import asyncio
import os
from typing import Any

from app import cache
from app.data.india_coast import nearest_coast
from app.providers import (
    aikosh,
    datagov,
    gdacs,
    gpm_imerg,
    hazards,
    imd,
    mosdac,
    nasa_power,
    open_meteo,
    openaq,
    openweather_air,
    port_signal,
    sachet,
    waqi,
)
from app.science.astro import at_pin as moon_at
from app.schemas.location import Location

def _blank_obs() -> dict[str, Any]:
    return {
        "om": {},
        "flood": {},
        "aqi": {},
        "marine": {},
        "nasa_precip": [],
        "caps": [],
        "official": None,
        "naqi": None,
        "mandi": [],
        "quakes": [],
        "tsunami": [],
        "aq_hist": [],
        "sachet": [],
        "port": {},
        "gdacs": [],
        "waqi": None,
        "ow_air": None,
        "om_models": {},
        "nasa_clim": {},
        "era5": {},
        "imerg": {},
        "mosdac": {},
        "status": {},
    }


async def gather_observations(
    loc: Location,
    *,
    enrich: bool = True,
    disabled: set[str] | None = None,
) -> dict[str, Any]:
    status: dict[str, str] = {}
    disabled = disabled or set()
    coast = nearest_coast(loc.lat, loc.lon)
    marine_stub = {
        "inland": coast["km"] > 250,
        "nearest_coast": coast["name"],
        "coast_km": coast["km"],
    }

    async def cached_nat(key: str, factory, ttl: float):
        async def run_f():
            val = factory() if callable(factory) else factory
            if asyncio.iscoroutine(val):
                return await val
            return val

        return await cache.aget(key, run_f, ttl_s=ttl, swr_s=ttl * 2)

    def is_disabled(name: str) -> bool:
        if name in disabled:
            return True
        if "open-meteo" in disabled and (name.startswith("open-meteo") or name == "era5"):
            return True
        if "open-meteo-air" in disabled and name == "openweather-air":
            return True
        if ("mosdac" in disabled or "sat_live" in disabled) and name == "gpm-imerg":
            return True
        if "data.gov.in-mandi" in disabled and name == "aikosh":
            return True
        if ("open-meteo-marine" in disabled or "science" in disabled) and name == "imd-port":
            return True
        return False

    async def run(name: str, coro, default, timeout: float = 4.5):
        if is_disabled(name):
            status[name] = "disabled"
            if asyncio.iscoroutine(coro):
                coro.close()
            return default
        try:
            val = await asyncio.wait_for(coro, timeout=timeout)
            if isinstance(val, dict) and val.get("_stale"):
                status[name] = "stale"
            else:
                status[name] = "ok"
            return val
        except Exception:
            status[name] = "error"
            return default

    async def run_pair(name: str, coro, default, timeout: float = 3.5):
        if is_disabled(name):
            status[name] = "disabled"
            if asyncio.iscoroutine(coro):
                coro.close()
            return default
        try:
            val, st = await asyncio.wait_for(coro, timeout=timeout)
            status[name] = st
            return val
        except Exception:
            status[name] = "error"
            return default

    async def nasa_precip():
        raw = await nasa_power.daily_point(loc.lat, loc.lon)
        return nasa_power.precip_series(raw)

    async def marine_bundle():
        coast = nearest_coast(loc.lat, loc.lon)
        if coast["km"] > 250:
            return {
                "inland": True,
                "nearest_coast": coast["name"],
                "coast_km": coast["km"],
            }
        raw = await open_meteo.marine(loc.lat, loc.lon)
        raw = dict(raw or {})
        raw["nearest_coast"] = coast["name"]
        raw["coast_km"] = coast["km"]
        need = raw.get("inland") or (raw.get("current") or {}).get("wave_height") is None
        if need and coast["km"] <= 150:
            near = await open_meteo.marine(coast["lat"], coast["lon"])
            if (near.get("current") or {}).get("wave_height") is not None:
                near = dict(near)
                near["nearest_coast"] = coast["name"]
                near["coast_km"] = coast["km"]
                near["inland"] = False
                near["snapped"] = True
                return near
        if (raw.get("current") or {}).get("wave_height") is not None:
            raw["inland"] = False
        cur = dict(raw.get("current") or {})
        if coast["km"] <= 80:
            off_lat, off_lon = (20.5, 88.0) if loc.lon >= 80 else (18.9, 72.6)
            off = await open_meteo.marine(off_lat, off_lon)
            ocur = off.get("current") or {}
            oh = ocur.get("wave_height")
            lh = cur.get("wave_height")
            use_off = oh is not None and (lh is None or float(oh) > float(lh or 0) * 1.15)
            if use_off:
                merged = dict(off)
                merged["nearest_coast"] = raw.get("nearest_coast") or coast["name"]
                merged["coast_km"] = raw.get("coast_km") if raw.get("coast_km") is not None else coast["km"]
                merged["inland"] = False
                merged["snapped"] = True
                merged["offshore"] = True
                merged["offshore_lat"] = off_lat
                merged["offshore_lon"] = off_lon
                return merged
        return raw

    if not enrich:
        om, caps = await asyncio.gather(
            run("open-meteo", open_meteo.forecast(loc.lat, loc.lon), {}, timeout=2.0),
            run("imd-cap", cached_nat("nat:imd-cap", imd.cap_alerts, 900), [], timeout=1.2),
        )
        out = _blank_obs()
        out["om"] = om
        out["caps"] = caps or []
        out["marine"] = marine_stub
        out["moon"] = moon_at(loc.lat, loc.lon)
        out["status"] = status
        return out

    (
        om,
        fl,
        aq,
        marine,
        nasa_p,
        caps,
        official,
        naqi,
        mandi,
        quakes,
        tsunami,
        _ak,
        aq_hist,
        gdacs_rows,
        waqi_row,
        ow_air,
        mosdac_st,
        sachet_rows,
        port,
        om_models,
        nasa_clim,
        era5,
        imerg_live,
    ) = await asyncio.gather(
        run("open-meteo", open_meteo.forecast(loc.lat, loc.lon), {}, timeout=4.0),
        run("open-meteo-flood", open_meteo.flood(loc.lat, loc.lon), {}, timeout=2.5),
        run("open-meteo-air", open_meteo.air_quality(loc.lat, loc.lon), {}, timeout=2.5),
        run("open-meteo-marine", marine_bundle(), {}, timeout=2.5),
        run("nasa-power", nasa_precip(), [], timeout=2.5),
        run("imd-cap", cached_nat("nat:imd-cap", imd.cap_alerts, 900), [], timeout=2.0),
        run_pair("imd-rest", imd.official_get("current_wx"), None, timeout=3.0),
        run_pair("data.gov.in-aqi", datagov.nearest_aqi(loc.lat, loc.lon, loc.state, loc.district, place=loc.place_name or loc.district), None, timeout=3.0),
        run_pair("data.gov.in-mandi", datagov.mandi_prices(loc.state, loc.district), [], timeout=3.0),
        run_pair("usgs-seismic", hazards.recent_quakes(loc.lat, loc.lon), [], timeout=2.5),
        run_pair("incois-tsunami", hazards.incois_tsunami(), [], timeout=2.0),
        run_pair("aikosh", aikosh.search_datasets("agriculture"), None, timeout=1.5),
        run_pair("openaq-hist", openaq.history(loc.lat, loc.lon), [], timeout=2.0),
        run_pair("gdacs", gdacs.events(), [], timeout=2.5),
        run_pair("waqi", waqi.nearest(loc.lat, loc.lon), None, timeout=2.5),
        run_pair("openweather-air", openweather_air.current(loc.lat, loc.lon), None, timeout=2.5),
        run("mosdac", mosdac.fetch_live(), {}, timeout=2.0),
        run_pair("sachet", sachet.alerts(loc.state), [], timeout=2.0),
        run_pair("imd-port", port_signal.hooghly(), {}, timeout=2.0),
        run("open-meteo-models", open_meteo.forecast_models(loc.lat, loc.lon), {}, timeout=3.0),
        run("nasa-power-clim", nasa_power.daily_years(loc.lat, loc.lon, 8), {}, timeout=2.5),
        run("era5", open_meteo.era5_context(loc.lat, loc.lon), {}, timeout=2.5),
        run("gpm-imerg", gpm_imerg.fetch_pin(loc.lat, loc.lon, heavy=False), {}, timeout=1.5),
    )
    mosdac_live = mosdac_st
    dg_ok = {status.get("data.gov.in-aqi"), status.get("data.gov.in-mandi")}
    status["data.gov.in"] = "ok" if "ok" in dg_ok else (status.get("data.gov.in-aqi") or "error")
    firms_fires: list = []
    if os.environ.get("PYTEST_CURRENT_TEST"):
        status["nasa-firms"] = "test-skip"
    else:
        try:
            from app.providers import firms as firms_prov

            fp = await asyncio.wait_for(firms_prov.fetch_india(), timeout=2.5)
            if isinstance(fp, dict):
                firms_fires = list(fp.get("fires") or [])
                status["nasa-firms"] = "ok" if fp.get("ok") else (fp.get("status") or "empty")
            else:
                status["nasa-firms"] = "empty"
        except Exception:
            status["nasa-firms"] = "error"
    return {
        "om": om,
        "flood": fl,
        "aqi": aq,
        "marine": marine,
        "nasa_precip": nasa_p,
        "caps": caps,
        "official": official,
        "naqi": naqi,
        "mandi": mandi,
        "quakes": quakes or [],
        "tsunami": tsunami or [],
        "aq_hist": aq_hist or [],
        "sachet": sachet_rows or [],
        "port": port or {},
        "gdacs": gdacs_rows or [],
        "waqi": waqi_row,
        "ow_air": ow_air,
        "moon": moon_at(loc.lat, loc.lon),
        "om_models": om_models if isinstance(om_models, dict) else {},
        "nasa_clim": nasa_clim if isinstance(nasa_clim, dict) else {},
        "era5": era5 if isinstance(era5, dict) else {},
        "imerg": imerg_live if isinstance(imerg_live, dict) else {},
        "mosdac": (mosdac_live if isinstance(mosdac_live, dict) and mosdac_live else mosdac_st) or {},
        "firms_fires": firms_fires,
        "status": status,
    }


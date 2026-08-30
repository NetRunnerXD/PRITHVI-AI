"""Assemble the VERA-MoE pack for the Models tab."""

from __future__ import annotations

from typing import Any

from app.ml.vera import cv_branch, fusion as fusion_mod, gate as gate_mod, historical as hist_mod
from app.ml.vera import extremes as extremes_mod, hourly as hourly_mod, mlops as mlops_mod
from app.ml.vera import preprocess, regime as regime_mod, temporal as temporal_mod, verify as verify_mod
from app.ml.vera import disagreement as disag_mod, intra_hour as intra_mod, leads as leads_mod, replays as replay_mod
from app.config import get_settings
from app.providers import graphcast_run, imd_gridded, mosdac
from app.providers import gpm_imerg


def api_needed() -> list[dict[str, Any]]:
    s = get_settings()
    out: list[dict[str, Any]] = []
    if not (s.mosdac_user and s.mosdac_pass):
        out.append(
            {
                "id": "mosdac",
                "env": ["MOSDAC_USER", "MOSDAC_PASS", "MOSDAC_BASE_URL"],
                "prompt": "Register at https://www.mosdac.gov.in, then add MOSDAC_USER, MOSDAC_PASS, and MOSDAC_BASE_URL=https://www.mosdac.gov.in to backend/.env to ingest INSAT-3D/3DR L1B HDF5. Until then the CV branch uses IMD 5-band Asia-sector JPEGs (VIS/SWIR/MIR/TIR/WV).",
            }
        )
    if not (s.nasa_earthdata_api or (s.nasa_earthdata_user and s.nasa_earthdata_pass)):
        out.append(
            {
                "id": "earthdata",
                "env": ["NASA_EARTHDATA_API"],
                "prompt": "Set NASA_EARTHDATA_API to an Earthdata user token (https://urs.earthdata.nasa.gov → Generate Token). Or NASA_EARTHDATA_USER + NASA_EARTHDATA_PASS. GIBS IMERG still runs without this.",
            }
        )
    if not s.cds_api_key:
        out.append(
            {
                "id": "cds",
                "env": ["CDS_API_KEY"],
                "prompt": "Optional Copernicus CDS key (https://cds.climate.copernicus.eu) for native ERA5 GRIB. Open-Meteo ERA5 archive already supplies 500 hPa / precip without a key.",
            }
        )
    if not s.graphcast_weights_dir:
        out.append(
            {
                "id": "graphcast_weights",
                "env": ["GRAPHCAST_WEIGHTS_DIR"],
                "prompt": "Optional: local GraphCast/Pangu/FourCastNet checkpoints. Live members already use Open-Meteo gfs_graphcast025, ecmwf_aifs025, and icon_seamless.",
            }
        )
    out.append(
        {
            "id": "imd_aws_arg",
            "locked": True,
            "env": [],
            "prompt": "IMD AWS/ARG hourly stations stay out of scope (portal locked since May 2025). Not required for VERA-MoE.",
        }
    )
    return out


GRAPH = {
    "nodes": [
        {"id": "data", "title": "Data sources", "layer": "DataSources"},
        {"id": "prep", "title": "Preprocess & harmonize", "layer": "Preprocessing"},
        {"id": "cv", "title": "Computer vision (INSAT)", "layer": "CVBranch"},
        {"id": "regime", "title": "Regime classifier", "layer": "RegimeDetection"},
        {"id": "hist", "title": "Historical patterns", "layer": "HistoricalModule"},
        {"id": "gate", "title": "Adaptive ViT gate", "layer": "AdaptiveGate"},
        {"id": "fusion", "title": "Extreme-preserving fusion", "layer": "Fusion"},
        {"id": "time", "title": "Multi-resolution temporal fusion", "layer": "TemporalFusion"},
        {"id": "out", "title": "Output products", "layer": "Output"},
        {"id": "mlops", "title": "Closed-loop MLOps", "layer": "MLOps"},
    ],
    "edges": [
        ["data", "prep"],
        ["prep", "cv"],
        ["prep", "regime"],
        ["prep", "hist"],
        ["cv", "gate"],
        ["regime", "gate"],
        ["hist", "gate"],
        ["prep", "gate"],
        ["gate", "fusion"],
        ["fusion", "time"],
        ["time", "out"],
        ["out", "mlops"],
        ["mlops", "gate"],
    ],
}


def build_vera(
    f: dict[str, Any],
    loc: Any,
    live_sat: dict[str, Any] | None,
    members: dict[str, dict] | None,
) -> dict[str, Any]:
    lat = float(getattr(loc, "lat", f.get("lat") or 0) or 0)
    lon = float(getattr(loc, "lon", f.get("lon") or 0) or 0)
    members = members or f.get("members") or {}
    member_ids = [k for k, v in members.items() if isinstance(v, dict)]
    gc = graphcast_run.status()
    members = graphcast_run.attach_members(dict(members)) if members else members
    member_ids = [k for k, v in members.items() if isinstance(v, dict)]

    insat = (live_sat or {}).get("insat") or {}
    cv_branch.try_persist_from_insat(insat)
    cv = cv_branch.run(live_sat, lat=lat, lon=lon)
    regime = regime_mod.classify(f, lat, lon)
    historical = hist_mod.run(f, lat, lon, regime)
    g = gate_mod.run(member_ids, members, cv, regime, historical, f, lead_hours=24.0)
    fus = fusion_mod.run(members, g.get("weights") or {}, historical)
    hourly = [float(x) for x in (f.get("hourly_precip") or [])[:48]]
    if len(hourly) < 48:
        q = float(fus.get("q50") or 0) / 24.0
        hourly = (hourly + [q] * 48)[:48]
    temp = temporal_mod.run(cv, fus, g, historical, hourly)
    loc_key = f"{round(lat, 3)},{round(lon, 3)}"
    hourly_rows = hourly_mod.build(f, members, g.get("weights") or {}, list(temp.get("hourly_0_48") or []), loc_key)
    try:
        perf = verify_mod.run(loc_key, hourly_rows, f)
    except OSError:
        perf = {"scores": {}, "cv": {"folds": 0}, "history": []}
    ens_mae = (perf.get("scores") or {}).get("ensemble", {}).get("mae") if perf.get("independent_obs") else None
    ops = mlops_mod.run(member_ids, str(regime.get("top")), fus, mae=ens_mae)
    moe_hourly = [hourly_mod.blend_hour(hourly_mod.member_hourly(members, h), g.get("weights") or {}) for h in range(48)]
    ext = extremes_mod.run(f, members, g.get("weights") or {}, fus, blend_hourly=moe_hourly)
    lead_rows = leads_mod.run(f, members, g.get("weights") or {})
    disag = disag_mod.run(members, fus, lead_rows)
    intra = intra_mod.run(f, blend_hourly=moe_hourly, ensemble_hourly=list(temp.get("hourly_0_48") or []))
    replay = replay_mod.run()
    loc_name = getattr(loc, "place_name", None) or getattr(loc, "district", None) or getattr(loc, "label", None) or "pin"
    rain24 = (lead_rows[0]["rain"] if lead_rows else {}).get("q50")
    flags = disag.get("flags") or []
    bulletin = (
        f"{loc_name}: 24 h blend rain {rain24 if rain24 is not None else '—'} mm (q50). "
        f"Regime {regime.get('top')}. "
        + (flags[0]["title"] + ". " if flags else "No disagreement flag. ")
        + f"Heat {(ext.get('heat_wave') or {}).get('level')}; wind {(ext.get('high_wind') or {}).get('level')}; "
        + f"heavy rain {(ext.get('heavy_rain') or {}).get('level')}. Automated; not a gauge."
    )
    from app.providers.imd_insat import ASIA_BOUNDS, INDIA_BOUNDS

    aw, ae, aso, an = ASIA_BOUNDS
    iw, ie, iso, inn = INDIA_BOUNDS
    der = cv.get("derived") or {}
    cv["map"] = {
        "stages": [
            {"id": "asia", "title": "1. Asia-sector frame", "note": "IMD INSAT Asiamer JPEG (40–110°E, 10°S–45°N)."},
            {"id": "india", "title": "2. India rectangle", "note": "downsample_india: lon 68.1–97.4°E, lat 6.6–35.8°N."},
            {"id": "mask", "title": "3. Political mask", "note": "Pixels outside india_mask set to 300 K."},
            {"id": "pin", "title": "4. Pin patch", "note": "13×13 IR sample around the search pin."},
            {"id": "cells", "title": "5. Convective cells", "note": "Cold-top segmentation + tracking."},
            {"id": "rain", "title": "6. IR rain-rate", "note": "Adler–Negri Tb proxy, not a rain-gauge."},
            {"id": "imerg", "title": "7. GPM IMERG", "note": "30-min 0.1° precipitation."},
            {"id": "motion", "title": "8. AMV / ConvLSTM", "note": "Block-match / hidden-state motion."},
            {"id": "weights", "title": "9. Gate RGB", "note": "9×9 spatial weights around the pin."},
        ],
        "asia": {"west": aw, "east": ae, "south": aso, "north": an, "url": "/api/sat/imd-asia", "source_url": cv.get("insat_url")},
        "india": {"west": iw, "east": ie, "south": iso, "north": inn},
        "pin": {"lat": lat, "lon": lon},
        "cells": cv.get("cells") or [],
        "amv": {"dx": der.get("amv_dx"), "dy": der.get("amv_dy")},
        "tb_k": cv.get("tb_k"),
        "heatmap": (cv.get("frames") or [{}])[-1].get("heatmap") if cv.get("frames") else None,
        "rain_url": cv.get("rain_url"),
        "gate_rgb": g.get("weight_map_rgb"),
        "imerg_wms": "https://gibs.earthdata.nasa.gov/wms/epsg3857/best/wms.cgi",
        "imerg_layer": "IMERG_Precipitation_Rate",
    }
    src = {
        "ecmwf_ifs": "open-meteo members / ECMWF",
        "gfs": "open-meteo members / GFS",
        "icon": "open-meteo members / ICON",
        "graphcast_pangu_fourcastnet": gc,
        "wrf_ncum": "Open-Meteo ukmo_global_deterministic_10km (regional NWP slot)",
        "mosdac": f.get("mosdac") or mosdac.status(),
        "gpm_imerg": gpm_imerg.status(),
        "imd_aws_arg": {"locked": True, "note": "Hourly station portal restricted since May 2025 — not ingested"},
        "imd_gridded": imd_gridded.status(),
        "era5": f.get("era5") or "open-meteo-era5-archive",
        "members": member_ids,
    }
    return {
        "name": "VERA-MoE",
        "title": "Vision-Enhanced Regime-Adaptive Mixture-of-Experts",
        "graph": GRAPH,
        "sources": src,
        "preprocess": preprocess.remap_note(lat, lon),
        "cv": cv,
        "regime": regime,
        "historical": historical,
        "gate": g,
        "fusion": fus,
        "temporal": temp,
        "outputs": {
            "hourly_0_48": temp.get("hourly_0_48"),
            "percentiles": {
                "p10": fus.get("q10"),
                "p25": fus.get("q25"),
                "p50": fus.get("q50"),
                "p75": fus.get("q75"),
                "p90": fus.get("q90"),
            },
            "hourly_p10": temp.get("p10"),
            "hourly_p90": temp.get("p90"),
            "extremes": fus.get("extremes"),
            "weight_map": g.get("weight_map_rgb"),
            "analogues": historical.get("analogues"),
        },
        "hourly": hourly_rows,
        "extremes": ext,
        "leads": lead_rows,
        "disagreement": disag,
        "intra_hour": intra,
        "replay": replay,
        "bulletin": bulletin,
        "performance": perf,
        "compare": {
            "hours": hourly_rows,
            "days": [
                {
                    "date": ((members.get(member_ids[0]) or {}).get("daily_times") or [None] * 7)[i] if member_ids else None,
                    "ensemble": fus.get("q50") if i == 0 else None,
                    "members": {sid: ((members.get(sid) or {}).get("precip_days") or [None])[i] if i < len((members.get(sid) or {}).get("precip_days") or []) else None for sid in member_ids},
                }
                for i in range(7)
            ],
        },
        "mlops": ops,
        "api_needed": api_needed(),
        "node_detail": {
            "data": src,
            "prep": preprocess.remap_note(lat, lon),
            "cv": {"input": cv.get("input"), "derived": cv.get("derived"), "channels": cv.get("channels")},
            "regime": regime,
            "hist": {"source": historical.get("source"), "n_days": historical.get("n_days"), "clim": historical.get("climatology")},
            "gate": {"method": g.get("method"), "weights": g.get("weights"), "by_window": g.get("by_window")},
            "fusion": {k: fus.get(k) for k in ("q10", "q25", "q50", "q75", "q90", "extremes", "mixture")},
            "time": temp.get("windows"),
            "out": {"percentiles": fus.get("q50"), "hourly_n": len(temp.get("hourly_0_48") or [])},
            "mlops": ops.get("registry"),
        },
    }

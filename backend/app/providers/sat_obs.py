"""Observation adapter for the between-scene Kalman.

MOSDAC INSAT HEM/IMR and NASA IMERG Early need credentials and are not
downloaded in this prototype (settings-only). Default scene is Open-Meteo
hourly analysis, labelled model-analysis — not a satellite, not a rain-gauge.

Native steps (when a legal public feed is wired later):
  INSAT-3D/3DR HEM/IMR  ~1800 s   (rapid-scan *imagery* ~270 s; QPE still 30 min)
  GPM IMERG Early       ~1800 s   (~4 h latency)
  GSMaP_NOW             ~1800 s
  Open-Meteo analysis   ~3600 s   (India minutely_15 is interpolated hourly)
"""

from __future__ import annotations

from typing import Any

from app.config import get_settings
from app.science.nowcast import _now, _parse


def from_open_meteo_hours(
    times: list[str],
    mm: list[float],
    *,
    past_only: bool = True,
    now_iso: str | None = None,
) -> dict[str, Any]:
    now = _parse(str(now_iso)) if now_iso else _now()
    knots: list[dict[str, Any]] = []
    for t, v in zip(times, mm):
        dt = _parse(str(t))
        if dt is None:
            continue
        if past_only and now is not None and dt > now:
            continue
        try:
            val = max(0.0, float(v))
        except (TypeError, ValueError):
            continue
        knots.append(
            {
                "t": str(t),
                "mm": round(val, 3),
                "mm_h": round(val, 3),
                "engine": "observed",
            }
        )
    return {
        "knots": knots,
        "source": "om-analysis",
        "source_kind": "model-analysis",
        "native_step_s": 3600,
        "note": "Open-Meteo hourly analysis. Not INSAT, not IMERG, not a rain-gauge.",
    }


def knots_from_nowcast(nc: dict[str, Any]) -> list[dict[str, Any]]:
    """Past hours only; never future NWP as a scene. Prefer the longer sat list."""
    sat_rows = list((nc.get("sat") or {}).get("obs_knots") or [])
    obs_rows = list(nc.get("observed") or [])
    rows = sat_rows if len(sat_rows) >= len(obs_rows) else obs_rows
    out: list[dict[str, Any]] = []
    for row in rows:
        try:
            val = float(row.get("mm_h") if row.get("mm_h") is not None else row.get("mm") or 0)
        except (TypeError, ValueError):
            continue
        t = row.get("t")
        if not t:
            continue
        out.append({"t": str(t), "mm": round(val, 3), "mm_h": round(val, 3), "engine": "observed"})
    return out


def from_imerg_rate(mm_h: float, t_iso: str | None = None) -> dict[str, Any]:
    now = _parse(str(t_iso)) if t_iso else _now()
    t = now.isoformat(timespec="seconds") if now else ""
    val = max(0.0, float(mm_h))
    return {
        "knots": [{"t": t, "mm": round(val, 3), "mm_h": round(val, 3), "engine": "observed"}],
        "source": "gibs-imerg",
        "source_kind": "satellite-qpe",
        "native_step_s": 1800,
        "note": "IMERG precipitation rate sampled from NASA GIBS.",
    }


def available_source() -> dict[str, Any]:
    s = get_settings()
    if s.mosdac_user and s.mosdac_pass:
        return {
            "source": "insat-hem",
            "source_kind": "satellite-qpe",
            "ready": False,
            "native_step_s": 1800,
            "note": "MOSDAC login present; HEM HDF not approved yet. Live path uses IMD INSAT IR JPEG + GIBS IMERG.",
        }
    return {
        "source": "imd-insat-ir + gibs-imerg",
        "source_kind": "satellite-ir",
        "ready": True,
        "native_step_s": 1800,
        "note": "Public IMD INSAT-3D/3DS IR1 JPEG + NASA GIBS IMERG. HEM HDF needs MOSDAC approval.",
    }

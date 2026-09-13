"""Orographic landslide watch from rain + soil + official wording.

Not a slope-stability model and not GSI. Himalayan / Western Ghats prior
plus 3-day rain and soil. Official CAP/Sachet 'landslide' text still wins.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from app.data.physiography import classify
from app.science.nowcast import _clip

IST = timezone(timedelta(hours=5, minutes=30))

HILL_STATES = {
    "Himachal Pradesh",
    "Uttarakhand",
    "Sikkim",
    "Arunachal Pradesh",
    "Meghalaya",
    "Nagaland",
    "Manipur",
    "Mizoram",
    "Tripura",
    "Jammu and Kashmir",
    "Ladakh",
    "Kerala",
    "Karnataka",
    "Tamil Nadu",
    "West Bengal",
    "Assam",
}


def _iso(dt: datetime) -> str:
    return dt.astimezone(IST).isoformat(timespec="minutes")


def nowcast(
    f: dict[str, Any],
    *,
    loc: Any = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    now = now or datetime.now(IST)
    rain3 = float(f.get("precip_3d_mm") or 0)
    rain1 = 0.0
    hourly = f.get("hourly_precip") or []
    i0 = int(f.get("hourly_now_i") or 0)
    if hourly:
        try:
            rain1 = float(hourly[max(0, min(i0, len(hourly) - 1))] or 0)
        except (TypeError, ValueError):
            rain1 = 0.0
    soil = float(f.get("soil_m3m3") or 0.28)
    phys = classify(
        float(getattr(loc, "lat", 0) or f.get("lat") or 0),
        float(getattr(loc, "lon", 0) or f.get("lon") or 0),
        loc=loc,
        state=getattr(loc, "state", None) if loc is not None else f.get("state"),
        district=getattr(loc, "district", None) if loc is not None else f.get("district"),
    )
    kind = str(phys.get("kind") or "")
    state = getattr(loc, "state", None) if loc is not None else f.get("state")
    hill = kind == "orographic" or ((state or "") in HILL_STATES and kind in {"orographic", "plateau", "hugli"})
    p = 0.04
    if hill:
        p += 0.18
    if kind == "orographic":
        p += 0.16
    p += _clip(rain3 / 90.0, 0.0, 0.42)
    if rain1 >= 8:
        p += 0.12
    elif rain1 >= 4:
        p += 0.06
    if soil >= 0.34:
        p += 0.10
    p = min(0.92, p)
    alert = bool(kind == "orographic" and rain3 >= 40 and p >= 0.55) or (hill and rain3 >= 70 and p >= 0.62)
    start = now
    level = "warning" if alert else ("watch" if p >= 0.35 and hill else "quiet")
    hours = 12 if alert else 6
    end = now + timedelta(hours=hours)
    watch = level in {"warning", "watch"}
    return {
        "kind": "landslide",
        "p": round(p, 3),
        "alert": alert,
        "level": level,
        "hill": hill,
        "phys": kind,
        "rain_3d_mm": round(rain3, 1),
        "soil_m3m3": round(soil, 3),
        "window_start": _iso(start) if watch else None,
        "window_end": _iso(end) if watch else None,
        "window_h": hours if watch else None,
        "method": "orographic + 3-day rain + soil (not GSI slope model)",
        "note": "Watch only. Official GSI/IMD landslide bulletins override.",
    }

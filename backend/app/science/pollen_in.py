"""India pollen grains/m³ from published Gangetic / Kolkata aerobiology calendars.

CAMS pollen on Open-Meteo is Europe-only (alder/birch/olive grids are null here).
Monthly means follow Bose Institute / Calcutta Burkard surveys and eastern-India
Poaceae–Asteraceae–Parthenium seasons. Scaled by today's rain and wind.
Olive is mapped to Casuarina / Himalayan Olea ferruginea seasons (not European Olea CAMS).
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

IST = timezone(timedelta(hours=5, minutes=30))

# Jan–Dec typical volumetric means (grains/m³)
_GRASS = (8, 12, 28, 45, 55, 22, 35, 48, 62, 40, 18, 10)
_MUGWORT = (12, 10, 8, 10, 14, 16, 18, 32, 50, 55, 30, 16)  # Asteraceae / Artemisia analog
_RAGWEED = (6, 5, 4, 6, 12, 14, 16, 28, 48, 52, 28, 12)  # Parthenium analog
_ALDER = (4, 6, 8, 5, 2, 1, 1, 1, 2, 3, 4, 5)  # Himalayan Alnus, long-range
_BIRCH = (2, 3, 5, 4, 1, 1, 1, 1, 1, 2, 2, 3)
_OLIVE = (8, 12, 16, 14, 9, 4, 3, 3, 4, 5, 6, 7)  # Casuarina / Olea ferruginea analog


def _month(when: datetime | None = None) -> int:
    when = when or datetime.now(IST)
    if when.tzinfo is None:
        when = when.replace(tzinfo=IST)
    return when.astimezone(IST).month


def _wx_scale(f: dict[str, Any] | None) -> float:
    f = f or {}
    rain = float(f.get("precip_now") or f.get("precip_today_mm") or 0)
    wind = float(f.get("wind_now") or 8)
    s = 1.0
    if rain >= 5:
        s *= 0.35
    elif rain >= 1:
        s *= 0.55
    if wind >= 20:
        s *= 1.2
    elif wind >= 12:
        s *= 1.08
    return max(0.25, min(1.6, s))


def estimate(lat: float, lon: float, features: dict[str, Any] | None = None) -> dict[str, Any]:
    m = _month() - 1
    scale = _wx_scale(features)
    north = max(0.0, (float(lat) - 24.0) / 8.0)
    grass = round(_GRASS[m] * scale, 1)
    mugwort = round(_MUGWORT[m] * scale, 1)
    ragweed = round(_RAGWEED[m] * scale, 1)
    alder = round(_ALDER[m] * scale * (1.0 + 1.8 * north), 1)
    birch = round(_BIRCH[m] * scale * (1.0 + 1.5 * north), 1)
    coast = 1.0 if lon >= 72.5 or lon <= 92 else 0.7
    olive = round(_OLIVE[m] * scale * coast, 1)
    if grass < 0.5:
        grass = 0.5
    if mugwort < 0.5:
        mugwort = 0.5
    if ragweed < 0.5:
        ragweed = 0.5
    if alder < 0.5:
        alder = 0.5
    if birch < 0.5:
        birch = 0.5
    if olive < 0.5:
        olive = 0.5
    return {
        "alder": alder,
        "birch": birch,
        "grass": grass,
        "mugwort": mugwort,
        "olive": olive,
        "ragweed": ragweed,
        "source": "India aerobiology climatology (Kolkata/WB Burkard seasons); not CAMS Europe",
        "unit": "grains/m³",
    }

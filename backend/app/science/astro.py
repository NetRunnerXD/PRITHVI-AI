"""Local moon phase and rise/set. Open-Meteo has no moon products."""

from __future__ import annotations

import math
from datetime import datetime, timedelta, timezone
from typing import Any

IST = timezone(timedelta(hours=5, minutes=30))


def _julian(dt: datetime) -> float:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    utc = dt.astimezone(timezone.utc)
    y, m, d = utc.year, utc.month, utc.day + (utc.hour + utc.minute / 60 + utc.second / 3600) / 24
    if m <= 2:
        y -= 1
        m += 12
    a = math.floor(y / 100)
    b = 2 - a + math.floor(a / 4)
    return math.floor(365.25 * (y + 4716)) + math.floor(30.6001 * (m + 1)) + d + b - 1524.5


def moon_illumination(dt: datetime) -> tuple[float, str]:
    """Synodic-month phase. Returns (illumination 0–1, name)."""
    jd = _julian(dt)
    syn = (jd - 2451550.1) / 29.530588853
    age = (syn - math.floor(syn)) * 29.530588853
    illum = 0.5 * (1 - math.cos(2 * math.pi * age / 29.530588853))
    if age < 1.84566:
        name = "new"
    elif age < 5.53699:
        name = "waxing crescent"
    elif age < 9.22831:
        name = "first quarter"
    elif age < 12.91963:
        name = "waxing gibbous"
    elif age < 16.61096:
        name = "full"
    elif age < 20.30228:
        name = "waning gibbous"
    elif age < 23.99361:
        name = "last quarter"
    elif age < 27.68493:
        name = "waning crescent"
    else:
        name = "new"
    return round(illum, 3), name


def _gmst_deg(jd: float) -> float:
    t = (jd - 2451545.0) / 36525.0
    return (280.46061837 + 360.98564736629 * (jd - 2451545.0) + 0.000387933 * t * t) % 360


def _moon_eq(jd: float) -> tuple[float, float]:
    t = (jd - 2451545.0) / 36525.0
    L = math.radians((218.316 + 481267.8812 * t) % 360)
    M = math.radians((134.963 + 477198.8676 * t) % 360)
    F = math.radians((93.272 + 483202.0175 * t) % 360)
    lon = L + math.radians(6.289 * math.sin(M))
    lat = math.radians(5.128 * math.sin(F))
    x = math.cos(lat) * math.cos(lon)
    y = math.cos(lat) * math.sin(lon)
    z = math.sin(lat)
    eps = math.radians(23.439 - 0.0000004 * t)
    ra = math.atan2(y * math.cos(eps) - z * math.sin(eps), x)
    dec = math.asin(y * math.sin(eps) + z * math.cos(eps))
    return math.degrees(ra) % 360, math.degrees(dec)


def moon_rise_set(lat: float, lon: float, day: datetime) -> dict[str, Any]:
    """Approximate IST moonrise/moonset for the calendar day (Meeus-lite)."""
    if day.tzinfo is None:
        day = day.replace(tzinfo=IST)
    local = day.astimezone(IST).replace(hour=0, minute=0, second=0, microsecond=0)
    rise = set_ = None
    prev = None
    for m in range(0, 24 * 60, 15):
        dt = local + timedelta(minutes=m)
        jd = _julian(dt)
        ra, dec = _moon_eq(jd)
        lst = (_gmst_deg(jd) + lon) % 360
        ha = ((lst - ra + 180) % 360) - 180
        alt = math.degrees(
            math.asin(
                math.sin(math.radians(lat)) * math.sin(math.radians(dec))
                + math.cos(math.radians(lat)) * math.cos(math.radians(dec)) * math.cos(math.radians(ha))
            )
        )
        if prev is not None:
            pa, _ = prev
            if pa < 0 <= alt and rise is None:
                rise = dt.isoformat(timespec="minutes")
            if pa >= 0 > alt and set_ is None:
                set_ = dt.isoformat(timespec="minutes")
        prev = (alt, dt)
    illum, name = moon_illumination(local + timedelta(hours=12))
    return {
        "moonrise": rise,
        "moonset": set_,
        "phase": name,
        "illumination": illum,
        "source": "local-meeus-lite (not WeatherAPI)",
    }


def at_pin(lat: float, lon: float, when: datetime | None = None) -> dict[str, Any]:
    when = when or datetime.now(IST)
    return moon_rise_set(lat, lon, when)

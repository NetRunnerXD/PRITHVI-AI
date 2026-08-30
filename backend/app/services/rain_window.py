"""Date-range daily rain from Open-Meteo. Numbers stay off the LLM."""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from app.providers import open_meteo
from app.schemas.location import Location
from app.science.nowcast import _now


def _f(v: Any, default: float | None = None) -> float | None:
    if v is None:
        return default
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


def _round(v: Any, n: int = 1) -> float | None:
    fv = _f(v)
    if fv is None:
        return None
    return round(fv, n)


async def fetch_window(loc: Location, start: date, end: date) -> dict[str, Any]:
    if end < start:
        start, end = end, start
    if (end - start).days > 16:
        end = start + timedelta(days=16)
    raw = await open_meteo.daily_window(loc.lat, loc.lon, start.isoformat(), end.isoformat())
    daily = raw.get("daily") or {}
    times = list(daily.get("time") or [])
    precip = list(daily.get("precipitation_sum") or [])
    probs = list(daily.get("precipitation_probability_max") or [])
    tmax = list(daily.get("temperature_2m_max") or [])
    tmin = list(daily.get("temperature_2m_min") or [])
    codes = list(daily.get("weather_code") or [])
    wmax = list(daily.get("wind_speed_10m_max") or [])
    wmean = list(daily.get("wind_speed_10m_mean") or [])
    wgust = list(daily.get("wind_gusts_10m_max") or [])
    wdir = list(daily.get("wind_direction_10m_dominant") or [])
    days: list[dict[str, Any]] = []
    have: set[str] = set()
    from app.ml.sky import sky_label

    def _at(seq: list, i: int) -> Any:
        return seq[i] if i < len(seq) else None

    for i, t in enumerate(times):
        p = _round(_at(precip, i))
        pr = _f(_at(probs, i))
        code = _at(codes, i)
        sky = None
        try:
            if code is not None:
                sky, _ = sky_label(int(code))
        except (TypeError, ValueError):
            sky = None
        days.append(
            {
                "date": str(t)[:10],
                "precip_mm": p,
                "precip_prob_pct": int(pr) if pr is not None else None,
                "temp_max_c": _round(_at(tmax, i)),
                "temp_min_c": _round(_at(tmin, i)),
                "weather_code": int(code) if code is not None else None,
                "sky_label": sky,
                "wind_speed_max_kmh": _round(_at(wmax, i)),
                "wind_speed_mean_kmh": _round(_at(wmean, i)),
                "wind_gust_max_kmh": _round(_at(wgust, i)),
                "wind_dir_deg": _round(_at(wdir, i), 0),
                "visibility": "not reported",
            }
        )
        have.add(str(t)[:10])
    days.sort(key=lambda r: r["date"])
    wanted: list[str] = []
    cur = start
    while cur <= end:
        wanted.append(cur.isoformat())
        cur += timedelta(days=1)
    missing = [d for d in wanted if d not in have]
    known = [float(r["precip_mm"]) for r in days if r.get("precip_mm") is not None]
    total = round(sum(known), 1) if known else None
    today = _now().date()
    horizon = today + timedelta(days=16)
    return {
        "location": loc.model_dump(),
        "start": start.isoformat(),
        "end": end.isoformat(),
        "days": days,
        "total_mm": total,
        "n": len(days),
        "missing": missing,
        "horizon": horizon.isoformat(),
        "source": "open-meteo daily",
        "source_kind": "model-forecast",
        "note": (
            "Open-Meteo daily precipitation_sum. Model forecast/analysis, not a rain-gauge, "
            "not INSAT. Forecast typically covers about 16 days from today."
        ),
        "method": "open-meteo daily window v1",
        "widget": "window",
    }


def format_en(pack: dict[str, Any]) -> str:
    loc = pack.get("location") or {}
    name = loc.get("place_name") or loc.get("district") or loc.get("label") or "this place"
    label = loc.get("label") or name
    start, end = pack.get("start"), pack.get("end")
    days = pack.get("days") or []
    lines = [
        f"Rainfall prediction for {label} from {start} to {end}.",
        "Open-Meteo daily model — not a rain-gauge and not a satellite.",
    ]
    for row in days:
        bit = f"{row['date']}: {row['precip_mm']} mm"
        if row.get("precip_prob_pct") is not None:
            bit += f" (chance {row['precip_prob_pct']}%)"
        if row.get("temp_max_c") is not None:
            bit += f", max {row['temp_max_c']}°C"
        lines.append(bit)
    if days:
        lines.append(f"Total over {len(days)} days: {pack.get('total_mm')} mm.")
    missing = pack.get("missing") or []
    if missing:
        lines.append("Not in the model horizon: " + ", ".join(missing) + ".")
    return "\n".join(lines)


def format_indic(pack: dict[str, Any], locale: str) -> str:
    loc = pack.get("location") or {}
    label = loc.get("label") or loc.get("place_name") or loc.get("district") or ""
    start, end = pack.get("start"), pack.get("end")
    days = pack.get("days") or []
    if locale == "bn":
        lines = [
            f"{label}: {start} থেকে {end} বৃষ্টির পূর্বাভাস।",
            "Open-Meteo দৈনিক মডেল — বৃষ্টিমাপক নয়, উপগ্রহ নয়।",
        ]
        for row in days:
            lines.append(f"{row['date']}: {row['precip_mm']} মিমি")
        if days:
            lines.append(f"{len(days)} দিনে মোট {pack.get('total_mm')} মিমি।")
        return "\n".join(lines)
    lines = [
        f"{label}: {start} से {end} बारिश का अनुमान।",
        "Open-Meteo दैनिक मॉडल — बारिश-गेज नहीं, उपग्रह नहीं।",
    ]
    for row in days:
        lines.append(f"{row['date']}: {row['precip_mm']} मिमी")
    if days:
        lines.append(f"{len(days)} दिनों में कुल {pack.get('total_mm')} मिमी।")
    return "\n".join(lines)

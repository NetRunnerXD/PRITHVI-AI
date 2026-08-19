"""Haldia live clock: 1-min gap series + 1 Hz playhead.

Gap millimetres integrate back to locked hourly knots.
Playhead seconds are clock / tide / ponding — never a new rain total.
"""

from __future__ import annotations

import json
import math
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from app.config import ROOT
from app.data.physiography import classify, hugli_relevant
from app.science.nowcast import IST, _clip, _now, _parse

LOG_PATH = Path(ROOT) / ".cache" / "nowcast_issues.jsonl"


def _pchip_slopes(xs: list[float], ys: list[float]) -> list[float]:
    n = len(xs)
    if n < 2:
        return [0.0] * n
    m = [0.0] * n
    for i in range(1, n - 1):
        d0 = (ys[i] - ys[i - 1]) / max(1e-9, xs[i] - xs[i - 1])
        d1 = (ys[i + 1] - ys[i]) / max(1e-9, xs[i + 1] - xs[i])
        m[i] = 0.0 if d0 * d1 <= 0 else 2.0 / (1.0 / d0 + 1.0 / d1)
    m[0] = (ys[1] - ys[0]) / max(1e-9, xs[1] - xs[0])
    m[-1] = (ys[-1] - ys[-2]) / max(1e-9, xs[-1] - xs[-2])
    return m


def _hermite(x0: float, x1: float, y0: float, y1: float, m0: float, m1: float, x: float) -> float:
    h = x1 - x0
    if h <= 0:
        return y0
    t = (x - x0) / h
    t2 = t * t
    t3 = t2 * t
    return (
        (2 * t3 - 3 * t2 + 1) * y0
        + (t3 - 2 * t2 + t) * h * m0
        + (-2 * t3 + 3 * t2) * y1
        + (t3 - t2) * h * m1
    )


def gap_series(hours: list[dict[str, Any]], *, dt_s: int = 60) -> dict[str, Any]:
    """1-min intensity shape. Sum of mm in each hour equals that hour's locked mm."""
    if not hours:
        return {
            "dt_s": dt_s,
            "series": [],
            "engine": "gap",
            "note": "1-min timing/shape. Integrates to locked hourly mm. Not a gauge.",
            "method": "pchip-renorm gap v1",
        }
    knots = []
    for i, h in enumerate(hours[:6]):
        dt = _parse(str(h.get("t") or ""))
        if dt is None:
            continue
        knots.append(
            {
                "t": h["t"],
                "dt": dt,
                "mm": max(0.0, float(h.get("mm") or 0)),
                "p_wet": float(h.get("p_wet") or 0.12),
                "engine": h.get("engine") or "nwp",
                "lead_h": int(h.get("lead_h") or i + 1),
            }
        )
    if not knots:
        return {"dt_s": dt_s, "series": [], "engine": "gap", "method": "pchip-renorm gap v1"}

    xs = [0.0]
    ys = [float(knots[0]["mm"])]
    acc = 0.0
    for i, k in enumerate(knots):
        acc += 1.0
        xs.append(acc)
        nxt = knots[i + 1]["mm"] if i + 1 < len(knots) else k["mm"] * 0.55
        ys.append(float(nxt))
    slopes = _pchip_slopes(xs, ys)

    series: list[dict[str, Any]] = []
    steps = max(1, int(round(3600 / dt_s)))
    for i, k in enumerate(knots):
        raw: list[float] = []
        for s in range(steps):
            frac = s / steps
            x = i + frac
            j = min(i, len(xs) - 2)
            rate = _hermite(xs[j], xs[j + 1], ys[j], ys[j + 1], slopes[j], slopes[j + 1], x)
            raw.append(max(0.0, rate))
        tot = sum(raw)
        target = float(k["mm"])
        if tot <= 1e-9:
            scaled = [target / steps] * steps if target else [0.0] * steps
        else:
            scaled = [v * target / tot for v in raw]
        for s, mm in enumerate(scaled):
            t = k["dt"] + timedelta(seconds=s * dt_s)
            series.append(
                {
                    "t": t.isoformat(timespec="seconds"),
                    "mm": round(mm, 4),
                    "mm_h": round(mm * (3600 / dt_s), 3),
                    "p_wet": round(_clip(k["p_wet"], 0.02, 0.95), 3),
                    "engine": "gap",
                    "parent_engine": k["engine"],
                    "lead_h": k["lead_h"],
                }
            )
    return {
        "dt_s": dt_s,
        "series": series,
        "engine": "gap",
        "note": "1-min timing/shape. Integrates to locked hourly mm. Not a gauge.",
        "method": "pchip-renorm gap v1",
        "checksum_mm": round(sum(p["mm"] for p in series), 3),
        "locked_mm": round(sum(k["mm"] for k in knots), 3),
    }


# Hugli M2-dominant prior. Labelled harmonics — not a SOI gauge.
_HUGLI: dict[str, dict[str, float]] = {
    "Haldia": {"lon": 88.07, "z0": 2.55, "m2": 1.55, "s2": 0.58, "k1": 0.16, "phase": 1.10},
    "Gangra": {"lon": 88.02, "z0": 2.40, "m2": 1.48, "s2": 0.55, "k1": 0.15, "phase": 1.02},
    "Sagar": {"lon": 88.05, "z0": 2.20, "m2": 1.35, "s2": 0.50, "k1": 0.14, "phase": 0.85},
    "Diamond Harbour": {"lon": 88.18, "z0": 2.70, "m2": 1.62, "s2": 0.60, "k1": 0.17, "phase": 1.25},
}


def hugli_station(lat: float | None, lon: float | None, name: str | None = None) -> str:
    blob = (name or "").lower()
    if "sagar" in blob:
        return "Sagar"
    if "diamond" in blob:
        return "Diamond Harbour"
    if "gangra" in blob:
        return "Gangra"
    if lat is None or lon is None:
        return "Haldia"
    if float(lat) < 21.78:
        return "Sagar"
    if float(lat) > 22.15:
        return "Diamond Harbour"
    return "Haldia"


def tide_height_m(dt: datetime, station: str = "Haldia") -> dict[str, Any]:
    p = _HUGLI.get(station) or _HUGLI["Haldia"]
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=IST)
    local = dt.astimezone(IST)
    hour = local.hour + local.minute / 60.0 + local.second / 3600.0
    m2 = 2 * math.pi * (hour / 12.42 + p["phase"] / (2 * math.pi))
    s2 = 2 * math.pi * (hour / 12.00 + p["phase"] / (2 * math.pi) + 0.08)
    k1 = 2 * math.pi * (hour / 23.93 + 0.2)
    h = p["z0"] + p["m2"] * math.sin(m2) + p["s2"] * math.sin(s2) + p["k1"] * math.sin(k1)
    high = math.sin(m2) > 0.55
    return {
        "tide_m": round(h, 3),
        "high_tide": high,
        "station": station,
        "source": "hugli_harmonics_v1",
        "note": "Named Hugli prior (Haldia/Gangra/Sagar). Not a Survey of India gauge.",
    }


def playhead(
    pack: dict[str, Any],
    *,
    now: datetime | None = None,
    loc: Any = None,
) -> dict[str, Any]:
    now = now or _now()
    gap = pack.get("gap") or {}
    series = list(gap.get("series") or [])
    clock = pack.get("clock") or {}
    pond = pack.get("ponding") or {}
    pump = pack.get("pump") or {}
    access = pack.get("access") or {}
    hy = pack.get("hysteresis") or {}
    place = pack.get("place") or {}
    lat = place.get("lat") if place.get("lat") is not None else getattr(loc, "lat", None)
    lon = place.get("lon") if place.get("lon") is not None else getattr(loc, "lon", None)
    name = place.get("name")
    show_tide = hugli_relevant(
        lat,
        lon,
        loc=loc,
        district=place.get("district"),
        place=name,
    ) or bool((pack.get("phys") or {}).get("show_tide"))
    station = hugli_station(lat, lon, name) if show_tide else None
    td = tide_height_m(now, station) if show_tide and station else {
        "tide_m": None,
        "high_tide": False,
        "station": None,
        "source": None,
        "note": "Hugli tide is not used off the estuary.",
    }
    onset = _parse(str(clock.get("t_start") or ""))
    secs = None
    if onset is not None:
        secs = int(round((onset - now).total_seconds()))
    pond_mm = 0.0
    factor = float(pond.get("factor") or 0.2)
    mm_now = 0.0
    mm_h = 0.0
    for row in series:
        dt = _parse(str(row.get("t") or ""))
        if dt is None:
            continue
        if dt <= now:
            pond_mm += float(row.get("mm") or 0) * factor
            mm_now = float(row.get("mm") or 0)
            mm_h = float(row.get("mm_h") or 0)
        else:
            break
    return {
        "t": now.astimezone(IST).isoformat(timespec="seconds"),
        "seconds_to_onset": secs,
        "tide_m": td.get("tide_m"),
        "tide_relevant": bool(show_tide),
        "high_tide": td.get("high_tide"),
        "tide_source": td.get("source"),
        "tide_station": station,
        "phys": (pack.get("phys") or classify(lat, lon, loc=loc)).get("kind"),
        "pond_mm": round(pond_mm, 3),
        "gap_mm": round(mm_now, 4),
        "gap_mm_h": round(mm_h, 3),
        "pump": pump.get("action"),
        "enterable": access.get("enterable"),
        "note": "1 Hz cursor / tide / countdown. gap_mm is the current 1-min bin, not a new forecast.",
        "method": "playhead v1",
    }


def attach_live(pack: dict[str, Any], loc: Any = None) -> dict[str, Any]:
    pack["gap"] = gap_series(pack.get("hours") or [])
    pack["playhead"] = playhead(pack, loc=loc)
    pack["live_note"] = (
        "Playhead ticks every second on the client. Rain timing finest is 1 minute. "
        "Hourly locked mm are the only totals the Advisor may quote."
    )
    return pack


def persist_issue(place_key: str, pack: dict[str, Any]) -> None:
    hours = pack.get("hours") or []
    if not hours:
        return
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    row = {
        "t": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "place": place_key,
        "regime": (pack.get("regime") or {}).get("name"),
        "mm": hours[0].get("mm"),
        "lead_h": hours[0].get("lead_h"),
        "engine": hours[0].get("engine"),
        "pump": (pack.get("pump") or {}).get("action"),
        "enterable": (pack.get("access") or {}).get("enterable"),
    }
    try:
        with LOG_PATH.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
    except OSError:
        return


def load_issues(place_key: str | None = None, limit: int = 168) -> list[dict[str, Any]]:
    if not LOG_PATH.exists():
        return []
    try:
        lines = LOG_PATH.read_text(encoding="utf-8").splitlines()
    except OSError:
        return []
    out: list[dict[str, Any]] = []
    for line in lines[-max(limit * 4, 200) :]:
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if place_key and row.get("place") != place_key:
            continue
        out.append(row)
    return out[-limit:]


def skill_from_log(rows: list[dict[str, Any]]) -> dict[str, Any]:
    by: dict[str, list[float]] = {}
    for a, b in zip(rows, rows[1:]):
        if a.get("regime") != b.get("regime"):
            continue
        try:
            issued = float(a.get("mm") or 0)
            obs = float(b.get("mm") or 0)
        except (TypeError, ValueError):
            continue
        if issued < 0.05 and obs < 0.05:
            continue
        by.setdefault(str(a.get("regime") or "x"), []).append(obs - issued)
    skill = {
        k: {"n": len(v), "mae_mm": round(sum(abs(x) for x in v) / len(v), 2)}
        for k, v in by.items()
        if v
    }
    return {
        "by_regime": skill,
        "n": sum(v["n"] for v in skill.values()),
        "method": "plus-1-issue log vs next issued hour (not an IMD gauge)",
        "imd_station_verify": {"available": False},
    }

"""48 h ensemble hourly rain vs Open-Meteo; write forecast rows to the verify log."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

IST = timezone(timedelta(hours=5, minutes=30))


def _now_hour() -> datetime:
    n = datetime.now(IST).replace(minute=0, second=0, microsecond=0)
    return n


def member_hourly(members: dict[str, dict], h: int) -> dict[str, float]:
    out: dict[str, float] = {}
    for sid, pack in members.items():
        ser = pack.get("hourly_precip") or pack.get("precip_hours") or []
        if h < len(ser):
            out[sid] = round(float(ser[h]), 3)
    return out


def blend_hour(vals: dict[str, float], weights: dict[str, float]) -> float:
    num = den = 0.0
    for sid, v in vals.items():
        w = float(weights.get(sid, 0))
        if w <= 0:
            w = 1.0
        num += v * w
        den += w
    return round(num / den, 3) if den else 0.0


def build(
    f: dict[str, Any],
    members: dict[str, dict],
    weights: dict[str, float],
    ensemble_hourly: list[float],
    loc_key: str,
) -> list[dict[str, Any]]:
    om = [float(x) for x in (f.get("hourly_precip") or [])[:48]]
    times = [str(x) for x in (f.get("hourly_times") or [])[:48]]
    start = _now_hour()
    rows = []
    for h in range(48):
        t = times[h] if h < len(times) else (start + timedelta(hours=h)).isoformat(timespec="minutes")
        mem = member_hourly(members, h)
        ens = ensemble_hourly[h] if h < len(ensemble_hourly) else blend_hour(mem, weights)
        om_h = om[h] if h < len(om) else None
        moe = blend_hour(mem, weights) if mem else ens
        rows.append(
            {
                "t": t,
                "lead_h": h,
                "ensemble": round(float(ens), 3),
                "moe": round(float(moe), 3),
                "om": round(float(om_h), 3) if om_h is not None else None,
                "members": mem,
                "pin": loc_key,
            }
        )
    return rows

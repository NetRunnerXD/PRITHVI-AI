"""Blended rain / temp / wind at 24, 72, 120, 240 h."""

from __future__ import annotations

from typing import Any

from app.ml.hybrid_blend import p_exceed, vincentize

LEADS_H = (24, 72, 120, 240)


def _days_for(lead_h: int) -> int:
    return max(1, int(round(lead_h / 24)))


def _slice(arr: list, n: int) -> list[float]:
    return [float(x) for x in (arr or [])[:n] if x is not None]


def _member_vals(members: dict[str, dict], key: str, n: int) -> tuple[list[str], list[float], list[float]]:
    ids, vals, ws = [], [], []
    for sid, pack in members.items():
        ser = pack.get(key) or []
        chunk = _slice(ser, n)
        if not chunk:
            continue
        ids.append(sid)
        if key in {"precip_days"}:
            vals.append(sum(chunk))
        elif key in {"temp_max", "wind_max", "wind_gust"}:
            vals.append(max(chunk))
        elif key in {"temp_min"}:
            vals.append(min(chunk))
        else:
            vals.append(sum(chunk) / len(chunk))
        ws.append(1.0)
    return ids, vals, ws


def run(f: dict[str, Any], members: dict[str, dict], weights: dict[str, float]) -> list[dict[str, Any]]:
    out = []
    for lead in LEADS_H:
        n = _days_for(lead)
        rain_om = sum(_slice(f.get("precip_days") or [], n))
        tmax_s = _slice(f.get("temp_max") or [], n)
        tmin_s = _slice(f.get("temp_min") or [], n)
        wind_s = _slice(f.get("wind_max") or [], n)
        gust_s = _slice(f.get("hourly_gust") or f.get("hourly_wind") or [], min(lead, 48))
        tmax_om = max(tmax_s) if tmax_s else None
        tmin_om = min(tmin_s) if tmin_s else None
        wind_om = max(wind_s) if wind_s else None
        gust_om = max(gust_s) if gust_s else wind_om

        def blend(key: str, om_v: float | None, thresh: float | None = None) -> dict[str, Any]:
            ids, vals, _ = _member_vals(members, key, n)
            ww = [float(weights.get(s, 1.0)) for s in ids] if ids else None
            q = vincentize(vals, ww) if vals else None
            p = p_exceed(vals, thresh, ww) if thresh is not None and vals else None
            def r2(x: float | None) -> float | None:
                return None if x is None else round(float(x), 2)

            return {
                "q10": r2(q["q10"] if q else om_v),
                "q50": r2(q["q50"] if q else om_v),
                "q90": r2(q["q90"] if q else om_v),
                "website": r2(om_v),
                "p_exceed": round(p, 2) if p is not None else None,
                "n_members": len(vals),
            }

        rain = blend("precip_days", rain_om, 64.5)
        tmax = blend("temp_max", tmax_om, 40.0)
        tmin = blend("temp_min", tmin_om)
        wind = blend("wind_max", wind_om, 60.0)
        out.append(
            {
                "lead_h": lead,
                "n_days": n,
                "rain": rain,
                "tmax": tmax,
                "tmin": tmin,
                "wind": wind,
                "gust_website": gust_om,
            }
        )
    return out

"""Hourly verification ledger vs Open-Meteo analysis. Rolling MAE and walk-forward CV."""

from __future__ import annotations

import json
import math
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from app.config import ROOT

LOG = ROOT / ".cache" / "vera_hourly_log.jsonl"
IST = timezone(timedelta(hours=5, minutes=30))


def _load() -> list[dict[str, Any]]:
    if not LOG.exists():
        return []
    rows = []
    try:
        for line in LOG.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    except OSError:
        return []
    return rows[-4000:]


def _save(rows: list[dict[str, Any]]) -> None:
    LOG.parent.mkdir(parents=True, exist_ok=True)
    LOG.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in rows[-4000:]) + "\n", encoding="utf-8")


def _hour_key(t: str) -> str:
    return str(t)[:13]


def _row_key(r: dict[str, Any]) -> str:
    lead = r.get("lead_h")
    lead_s = str(int(lead)) if lead is not None else ""
    return f"{r.get('pin')}|{_hour_key(str(r.get('t')))}|{lead_s}"


def ingest_forecast(rows: list[dict[str, Any]]) -> None:
    prev = _load()
    idx = {_row_key(r): i for i, r in enumerate(prev)}
    for r in rows:
        k = _row_key(r)
        if k in idx:
            old = prev[idx[k]]
            if old.get("obs") is not None:
                r = {**r, "obs": old.get("obs"), "obs_source": old.get("obs_source")}
            prev[idx[k]] = r
        else:
            prev.append(r)
            idx[k] = len(prev) - 1
    _save(prev)


def backfill_obs(
    pin: str,
    hourly_times: list[str],
    obs_hourly: list[float],
    now: datetime | None = None,
    source: str = "independent",
) -> int:
    """Attach past-hour observations. Never use the Open-Meteo forecast series as obs."""
    now = now or datetime.now(IST)
    prev = _load()
    n = 0
    by_t = {str(t)[:13]: float(p) for t, p in zip(hourly_times, obs_hourly)}
    for r in prev:
        if r.get("pin") != pin:
            continue
        ts = str(r.get("t") or "")
        if len(ts) < 13:
            continue
        try:
            ht = datetime.fromisoformat(ts.replace("Z", "+00:00"))
            if ht.tzinfo is None:
                ht = ht.replace(tzinfo=IST)
        except ValueError:
            continue
        if ht >= now:
            continue
        key = ts[:13]
        if key in by_t and r.get("obs") is None:
            r["obs"] = by_t[key]
            r["obs_source"] = source
            n += 1
    if n:
        _save(prev)
    return n


def _mae_rmse(pairs: list[tuple[float, float]]) -> dict[str, float]:
    if not pairs:
        return {"mae": None, "rmse": None, "n": 0}
    ae = [abs(a - b) for a, b in pairs]
    se = [(a - b) ** 2 for a, b in pairs]
    n = len(pairs)
    return {"mae": round(sum(ae) / n, 4), "rmse": round(math.sqrt(sum(se) / n), 4), "n": n}


def scores(pin: str) -> dict[str, Any]:
    rows = [r for r in _load() if r.get("pin") == pin and r.get("obs") is not None]
    ens = _mae_rmse([(float(r["ensemble"]), float(r["obs"])) for r in rows if r.get("ensemble") is not None])
    members: dict[str, dict] = {}
    ids: set[str] = set()
    for r in rows:
        ids.update((r.get("members") or {}).keys())
    for sid in ids:
        pairs = []
        for r in rows:
            v = (r.get("members") or {}).get(sid)
            if v is not None:
                pairs.append((float(v), float(r["obs"])))
        members[sid] = _mae_rmse(pairs)
    om = _mae_rmse([(float(r["om"]), float(r["obs"])) for r in rows if r.get("om") is not None])
    best = None
    best_mae = 1e9
    for sid, sc in members.items():
        if sc.get("mae") is not None and sc["mae"] < best_mae:
            best_mae = sc["mae"]
            best = sid
    moe = _mae_rmse([(float(r["moe"]), float(r["obs"])) for r in rows if r.get("moe") is not None])
    skill = None
    independent = bool(rows) and all(
        str(r.get("obs_source") or "") not in {"open-meteo-analysis", "open-meteo", ""} for r in rows
    )
    if independent and ens.get("mae") is not None and om.get("mae"):
        skill = round(1.0 - ens["mae"] / max(om["mae"], 1e-6), 3)
    by_lead: dict[str, dict] = {}
    bins = ((0, 2, "0-2"), (3, 6, "3-6"), (6, 24, "6-24"), (24, 48, "24-48"))
    for lo, hi, name in bins:
        grp = [r for r in rows if r.get("lead_h") is not None and lo <= int(r["lead_h"]) < hi]
        by_lead[name] = _mae_rmse([(float(r["ensemble"]), float(r["obs"])) for r in grp if r.get("ensemble") is not None])
    return {
        "ensemble": ens,
        "moe": moe,
        "open_meteo": om,
        "members": members,
        "best_member": best,
        "skill_vs_om": skill,
        "by_lead": by_lead,
        "independent_obs": independent,
    }


def walk_forward_cv(pin: str, fold_h: int = 12) -> dict[str, Any]:
    rows = [r for r in _load() if r.get("pin") == pin and r.get("obs") is not None and r.get("ensemble") is not None]
    rows.sort(key=lambda r: str(r.get("t")))
    if len(rows) < fold_h * 2:
        return {"folds": 0, "mae_mean": None, "mae_std": None, "note": "need more verified hours"}
    fold_maes = []
    i = fold_h
    while i + fold_h <= len(rows):
        test = rows[i : i + fold_h]
        ae = [abs(float(r["ensemble"]) - float(r["obs"])) for r in test]
        fold_maes.append(sum(ae) / len(ae))
        i += fold_h
    if not fold_maes:
        return {"folds": 0, "mae_mean": None, "mae_std": None}
    mu = sum(fold_maes) / len(fold_maes)
    var = sum((x - mu) ** 2 for x in fold_maes) / len(fold_maes)
    return {
        "folds": len(fold_maes),
        "fold_hours": fold_h,
        "mae_mean": round(mu, 4),
        "mae_std": round(math.sqrt(var), 4),
        "method": "frozen-weights rolling-origin on held-out valid hours (not a re-gated k-fold)",
    }


def history(pin: str) -> list[dict[str, Any]]:
    rows = [r for r in _load() if r.get("pin") == pin and r.get("obs") is not None]
    by_day: dict[str, list] = {}
    for r in rows:
        d = str(r.get("t"))[:10]
        by_day.setdefault(d, []).append(r)
    out = []
    for d, grp in sorted(by_day.items())[-14:]:
        ens = _mae_rmse([(float(r["ensemble"]), float(r["obs"])) for r in grp])
        mem: dict[str, float] = {}
        ids: set[str] = set()
        for r in grp:
            ids.update((r.get("members") or {}).keys())
        for sid in ids:
            sc = _mae_rmse(
                [(float((r.get("members") or {}).get(sid)), float(r["obs"])) for r in grp if (r.get("members") or {}).get(sid) is not None]
            )
            if sc.get("mae") is not None:
                mem[sid] = sc["mae"]
        out.append({"date": d, "ensemble_mae": ens.get("mae"), "n": ens.get("n"), "members": mem})
    return out


def agreement(pin: str) -> dict[str, Any]:
    """Forecast-vs-Open-Meteo closeness (not gauge skill). Always available."""
    rows = [r for r in _load() if r.get("pin") == pin and r.get("om") is not None]
    ens = _mae_rmse([(float(r["ensemble"]), float(r["om"])) for r in rows if r.get("ensemble") is not None])
    moe = _mae_rmse([(float(r["moe"]), float(r["om"])) for r in rows if r.get("moe") is not None])
    members: dict[str, dict] = {}
    ids: set[str] = set()
    for r in rows:
        ids.update((r.get("members") or {}).keys())
    for sid in ids:
        pairs = [(float((r.get("members") or {}).get(sid)), float(r["om"])) for r in rows if (r.get("members") or {}).get(sid) is not None]
        members[sid] = _mae_rmse(pairs)
    eq_pairs = []
    for r in rows:
        mems = r.get("members") or {}
        if mems and r.get("om") is not None:
            eq_pairs.append((sum(float(v) for v in mems.values()) / len(mems), float(r["om"])))
    equal = _mae_rmse(eq_pairs)
    best = None
    best_mae = 1e9
    for sid, sc in members.items():
        if sc.get("mae") is not None and sc["mae"] < best_mae:
            best_mae, best = sc["mae"], sid
    return {
        "ensemble": ens,
        "moe": moe,
        "equal_weight": equal,
        "members": members,
        "best_member": best,
        "n": ens.get("n") or 0,
        "vs": "open-meteo",
    }


def hourly_history(pin: str, n: int = 48) -> list[dict[str, Any]]:
    rows = [r for r in _load() if r.get("pin") == pin]
    rows.sort(key=lambda r: (str(r.get("t")), int(r.get("lead_h") or 0)))
    out = []
    for r in rows[-n:]:
        out.append(
            {
                "t": r.get("t"),
                "lead_h": r.get("lead_h"),
                "ensemble": r.get("ensemble"),
                "moe": r.get("moe"),
                "om": r.get("om"),
                "obs": r.get("obs"),
            }
        )
    return out


def _independent_series(f: dict[str, Any]) -> tuple[list[str], list[float], str] | None:
    times = [str(x) for x in (f.get("hourly_times") or [])]
    for key, src in (("imerg_hourly", "gpm-imerg"), ("obs_hourly", "independent"), ("hem_hourly", "mosdac-hem")):
        ser = f.get(key)
        if isinstance(ser, list) and ser and times:
            return times, [float(x) for x in ser], src
    return None


def run(pin: str, forecast_rows: list[dict[str, Any]], f: dict[str, Any]) -> dict[str, Any]:
    ingest_forecast(forecast_rows)
    n_back = 0
    obs_src = None
    indep = _independent_series(f)
    if indep:
        times, precip, obs_src = indep
        n_back = backfill_obs(pin, times, precip, source=obs_src)
    sc = scores(pin)
    agr = agreement(pin)
    verified = int(sc.get("ensemble", {}).get("n") or 0)
    independent = bool(sc.get("independent_obs")) and verified > 0
    return {
        "scores": sc,
        "cv": walk_forward_cv(pin),
        "history": history(pin),
        "hourly_history": hourly_history(pin),
        "agreement": agr,
        "n_logged": len([r for r in _load() if r.get("pin") == pin]),
        "n_verified": verified if independent else 0,
        "backfilled": n_back,
        "obs_source": obs_src or "none — Open-Meteo forecast is not used as truth",
        "independent_obs": independent,
        "note": None
        if independent
        else "Skill vs Open-Meteo is omitted until IMERG/HEM/gauge hours are backfilled. OM is the NWP reference, not obs.",
        "cost_loss": _cost_loss(sc, f),
        "leaderboard": _leaderboard(agr),
    }


def _cost_loss(sc: dict[str, Any], f: dict[str, Any]) -> dict[str, Any]:
    p = 0.0
    days = f.get("precip_days") or []
    if days and float(days[0] or 0) >= 64.5:
        p = 0.7
    elif days:
        p = min(0.45, float(days[0] or 0) / 80.0)
    cl = 0.3
    warn = p * (1 - cl) - (1 - p) * cl
    return {
        "p_event": round(p, 3),
        "cost_loss_ratio": cl,
        "value_vs_never": round(max(0.0, warn), 3),
        "note": "Relative value of a heavy-rain warning vs never warning. Not rupees. C/L=0.3.",
    }


def _leaderboard(agr: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    if agr.get("ensemble", {}).get("mae") is not None:
        rows.append({"id": "ensemble", "family": "ensemble", "mae": agr["ensemble"]["mae"]})
    if agr.get("moe", {}).get("mae") is not None:
        rows.append({"id": "blend", "family": "blend", "mae": agr["moe"]["mae"]})
    if agr.get("equal_weight", {}).get("mae") is not None:
        rows.append({"id": "equal_weight", "family": "baseline", "mae": agr["equal_weight"]["mae"]})
    for sid, sc in (agr.get("members") or {}).items():
        if sc.get("mae") is not None:
            fam = "ai" if any(k in sid.lower() for k in ("graphcast", "pangu", "fourcast", "aifs")) else "nwp"
            rows.append({"id": sid, "family": fam, "mae": sc["mae"]})
    rows.sort(key=lambda r: r["mae"])
    return rows

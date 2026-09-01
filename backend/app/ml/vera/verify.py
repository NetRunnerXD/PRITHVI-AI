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
    """First write wins for issued millimetres. Later OM rewrites do not replace them."""
    prev = _load()
    idx = {_row_key(r): i for i, r in enumerate(prev)}
    now = datetime.now(IST).isoformat(timespec="seconds")
    frozen_new: list[dict[str, Any]] = []
    for r in rows:
        r = dict(r)
        r.setdefault("issued_at", now)
        if r.get("om_issued") is None:
            r["om_issued"] = r.get("om")
        k = _row_key(r)
        if k in idx:
            old = prev[idx[k]]
            keep = {
                **r,
                "ensemble": old.get("ensemble", r.get("ensemble")),
                "moe": old.get("moe", r.get("moe")),
                "om": old.get("om_issued", old.get("om", r.get("om"))),
                "om_issued": old.get("om_issued", old.get("om", r.get("om"))),
                "members": old.get("members") if old.get("members") is not None else r.get("members"),
                "issued_at": old.get("issued_at") or r.get("issued_at"),
            }
            if old.get("obs") is not None:
                keep["obs"] = old.get("obs")
                keep["obs_source"] = old.get("obs_source")
            prev[idx[k]] = keep
        else:
            prev.append(r)
            idx[k] = len(prev) - 1
            frozen_new.append(r)
    _save(prev)
    if frozen_new:
        try:
            from app.ml.vera.issue_store import upsert_frozen

            upsert_frozen(frozen_new)
        except Exception:
            pass


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
            try:
                from app.ml.vera.issue_store import set_obs

                set_obs(pin, key, r.get("lead_h"), by_t[key], source)
            except Exception:
                pass
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


def om_blend_pack(pin: str, n: int = 48) -> dict[str, Any]:
    """Blend vs Open-Meteo as issued. Skill only when independent obs exist."""
    rows = [r for r in _load() if r.get("pin") == pin]
    rows.sort(key=lambda r: (str(r.get("t")), int(r.get("lead_h") or 0)))
    issued = []
    for r in rows[-n:]:
        om_i = r.get("om_issued")
        if om_i is None:
            om_i = r.get("om")
        issued.append(
            {
                "t": r.get("t"),
                "lead_h": r.get("lead_h"),
                "issued_at": r.get("issued_at"),
                "blend": r.get("moe"),
                "ensemble": r.get("ensemble"),
                "om_issued": om_i,
                "obs": r.get("obs"),
                "obs_source": r.get("obs_source"),
            }
        )
    agr = _mae_rmse(
        [
            (float(r["blend"]), float(r["om_issued"]))
            for r in issued
            if r.get("blend") is not None and r.get("om_issued") is not None
        ]
    )
    indep = [
        r
        for r in issued
        if r.get("obs") is not None and str(r.get("obs_source") or "") not in {"open-meteo-analysis", "open-meteo", ""}
    ]
    blend_obs = _mae_rmse([(float(r["blend"]), float(r["obs"])) for r in indep if r.get("blend") is not None])
    om_obs = _mae_rmse([(float(r["om_issued"]), float(r["obs"])) for r in indep if r.get("om_issued") is not None])
    skill = None
    if blend_obs.get("mae") is not None and om_obs.get("mae"):
        skill = round(1.0 - float(blend_obs["mae"]) / max(float(om_obs["mae"]), 1e-6), 3)
    by_lead: dict[str, Any] = {}
    bins = ((0, 2, "0-2"), (3, 6, "3-6"), (6, 24, "6-24"), (24, 48, "24-48"))
    for lo, hi, name in bins:
        grp = [r for r in indep if r.get("lead_h") is not None and lo <= int(r["lead_h"]) < hi]
        by_lead[name] = {
            "blend": _mae_rmse([(float(r["blend"]), float(r["obs"])) for r in grp if r.get("blend") is not None]),
            "om": _mae_rmse([(float(r["om_issued"]), float(r["obs"])) for r in grp if r.get("om_issued") is not None]),
        }
    return {
        "issued_rows": issued,
        "agreement_mae": agr.get("mae"),
        "agreement_n": agr.get("n") or 0,
        "skill_vs_om": skill,
        "blend_mae_vs_obs": blend_obs.get("mae"),
        "om_mae_vs_obs": om_obs.get("mae"),
        "n_issued": len(issued),
        "n_verified": len(indep),
        "by_lead": by_lead,
        "independent_obs": bool(indep),
        "note": None
        if indep
        else "Agreement is blend vs Open-Meteo locked at issue time. Not skill until IMERG/HEM/ERA5 fills obs.",
    }


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
        "om_blend": om_blend_pack(pin),
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
        "pinball": _pinball_scores(pin) if independent else None,
        "walk_forward": walk_forward_cv(pin),
    }


def _pinball_scores(pin: str) -> dict[str, Any]:
    from app.ml.vera.fusion import QUANTILES, pinball_mean

    rows = [r for r in _load() if r.get("pin") == pin and r.get("obs") is not None and r.get("moe") is not None]
    if not rows:
        return {"n": 0}
    y = [float(r["obs"]) for r in rows]
    yhat = [float(r["moe"]) for r in rows]
    by_tau = {str(t): pinball_mean(y, yhat, t) for t in QUANTILES}
    return {"n": len(rows), "by_tau": by_tau, "note": "Pinball of blend vs independent obs only."}


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

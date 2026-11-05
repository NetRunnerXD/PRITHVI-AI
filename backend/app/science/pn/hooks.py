"""Hook points for the next PN layers (all OFF by default; no-ops until models are wired).

  PN-Judge (0–3 h)      PN_JUDGE_ENABLED=1   per-lead class RAIN / NO_RAIN / UNCERTAIN on the v7 field
  PN-Correct (6–12 h)   PN_CORRECT_ENABLED=1 separate "rain within 25 km" layer at 6/9/12 h (pn/correct.py)
  Hand-over (4–7 h)     weight of the v7 nowcast vs PN-Correct per lead — frozen at 1.0 (nowcast only)

PN-Judge failed its pre-registered test: not wired, hook stays a no-op even with the flag set.
PN-Correct is a separate layer with its own target; it never replaces or blends into the v7 field.
  judge ctx   = {"t_issue", "rain_q" [6,H,W], "nwp" (nwp_v7.build output), "out" (v7.run output)}
  correct ctx = {"t_issue", "pnc" (nwp_v7.build_correct_runs + IMERG "obs")}
Hooks return None when disabled, so the v7 pack is unchanged.
"""

from __future__ import annotations

import time
from datetime import UTC, timedelta
from typing import Any

import numpy as np

from app.science.pn import _flag

HANDOVER_LEADS = (4, 5, 6, 7)


def judge_enabled() -> bool:
    return _flag("PN_JUDGE_ENABLED", False)


def correct_enabled() -> bool:
    return _flag("PN_CORRECT_ENABLED", False)


def judge(ctx: dict[str, Any]) -> dict[int, dict[str, Any]] | None:
    """{lead: {"class": "RAIN"|"NO_RAIN"|"UNCERTAIN", ...}} for leads 1..3, or None."""
    if not judge_enabled():
        return None
    return None  # model not wired yet (export_v7_app/INTEGRATION.md)


def correct(ctx: dict[str, Any]) -> dict[str, Any] | None:
    """PN-Correct layer {ok, leads: [{lead_h, valid_start, cut, n_cells_0p25, cells(0.5°)}], ...} or None."""
    if not correct_enabled():
        return None
    from app.science.pn import correct as pnc

    st = pnc.status()
    if not st["enabled"]:
        return {"ok": False, "status": "unavailable", "needs": st["needs"]}
    inp = ctx.get("pnc") or {}
    if inp.get("error") or "gfs_run" not in inp:
        return {"ok": False, "status": "error", "error": inp.get("error", "no inputs")}
    T = ctx["t_issue"]
    try:
        t0 = time.time()
        r = pnc.run(T, inp)
        ms = round((time.time() - t0) * 1000)
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "status": "error", "error": str(e)[:160]}
    try:
        from app import cache

        cache.set("pn7:pnc:last", {"t_issue": T, "p": np.round(r["p_rain"] * 250).astype(np.uint8)}, 6 * 3600)
    except Exception:  # noqa: BLE001
        pass
    c = pnc.cfg()
    leads = []
    for k, L in enumerate(pnc.LEADS):
        vs = (T + timedelta(hours=L - 1)).replace(tzinfo=UTC)
        leads.append({"lead_h": L, "valid_start": vs.isoformat(), "cut": float(c["cut"][str(L)]), "test_csi": c["test_0p25"][str(L)]["csi"],
                      "n_cells_0p25": int(r["event"][k].sum()), "cells": pnc.cells(r["event"][k], r["p_rain"][k])})
    return {"ok": True, "status": "ok", "model": "PN-Correct v6 (ONNX CPU)", "target": "rain ≥ 1 mm/h within 25 km",
            "t_issue": T.replace(tzinfo=UTC).isoformat(), "run_ms": ms, "inputs": r["inputs"],
            "runs": {"gfs": f"{inp['gfs_run']:%Y%m%d%H}", "ifs": f"{inp['ifs_run']:%Y%m%d%H}"},
            "errors": inp.get("errors") or [], "leads": leads}


def handover_weight(lead_h: int, corrected_available: bool) -> float:
    """Weight on the v7 nowcast at this lead (rest goes to PN-Correct). Nowcast only unless PN-Correct ran."""
    return 1.0  # frozen: PN-Correct is a separate layer, not blended into the v7 field


def status() -> dict[str, Any]:
    from app.science.pn import correct as pnc

    return {"pn_judge": {"flag": judge_enabled(), "wired": False, "note": "failed pre-registered test"},
            "pn_correct": {**pnc.status(), "wired": True}, "handover_weight": 1.0}

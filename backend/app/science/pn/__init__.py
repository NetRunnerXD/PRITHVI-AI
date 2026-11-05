"""PRITHVI research methods (PN-*) brought into the app pipeline.

Source: NetRunnerXD/PRITHVI-AI-Research, branch `severe-weather-nowcast`.

* PN-Blend (rain, 1–12 h): fixed per-lead weights for extrapolation / GFS / ECMWF IFS
  tuned on validation in the research repo — pure post-processing, no weights, always on
  unless PN_BLEND_ENABLED=0.
* PN-Blend (cyclone track, 12 h): extrapolation .35 / GFS .20 / IFS .45 (see cyclones.py).
* PN-Net v4 (ConvLSTM) — ONNX CPU inference behind PN_ENABLED + PN_MODEL_PATH. Needs real
  hourly IMERG (NASA Earthdata) and, for best skill, INSAT L1C Tb (MOSDAC). Groups that are
  missing are passed with their availability-mask channel = 0, as in training.
* PRITHVI-Nowcast v7 (R2 + PN-Blend) — PN_ENABLED=1 + PN_VERSION=v7 (+ PN_V7_MODEL_PATH); IMERG
  + live GFS/IFS (latency rule), INSAT masked. v4 stays the default engine.
* PN-Judge / PN-Correct: hook points in pn/hooks.py, off unless PN_JUDGE_ENABLED / PN_CORRECT_ENABLED.
"""

from __future__ import annotations

import json
import os
from functools import lru_cache
from pathlib import Path
from typing import Any

_PARAMS = Path(__file__).with_name("research_params.json")


@lru_cache(maxsize=1)
def params() -> dict[str, Any]:
    return json.loads(_PARAMS.read_text(encoding="utf-8"))


def _flag(name: str, default: bool) -> bool:
    v = os.environ.get(name)
    if v is None:
        return default
    return v.strip().lower() in {"1", "true", "yes", "on"}


def blend_enabled() -> bool:
    return _flag("PN_BLEND_ENABLED", True)


def net_enabled() -> bool:
    return _flag("PN_ENABLED", False)


def status() -> dict[str, Any]:
    """What is wired, what is missing (env var NAMES only, never values)."""
    from app.science.pn import hooks, net, v7

    ns = net.status()
    return {
        "pn_blend_rain": {"enabled": blend_enabled(), "needs": []},
        "pn_blend_cyclone": {"enabled": blend_enabled(), "needs": []},
        "pn_net": ns,
        "pn_nowcast_v7": v7.status(),
        "engine": v7.version(),
        "hooks": hooks.status(),
        "pn_correct": _correct_status(),
        "pn_judge": {"enabled": False, "wired": False, "note": "failed its pre-registered test; not wired"},
        "source": params().get("source"),
    }


def _correct_status() -> dict[str, Any]:
    try:
        from app.science.pn import correct

        return correct.status()
    except Exception as e:  # noqa: BLE001
        return {"enabled": False, "needs": [type(e).__name__]}


def science_summary(lat: float | None = None, lon: float | None = None) -> dict[str, Any]:
    """Compact v7 card for the Science panel: test CSI, live groups, live track (cached, non-blocking).
    With PN_CORRECT_ENABLED=1 also the separate PN-Correct 'rain within 25 km' values at (lat, lon)."""
    try:
        from app.science.pn import live, v7
        from app.store import pn_runs

        t = params()["pn_nowcast_v7"]["test_by_lead_h"]
        out: dict[str, Any] = {
            "model": "PRITHVI-Nowcast v7",
            "test_csi": {L: t[L]["final"]["csi"] for L in ("1", "3", "6", "12")},
            "beats": ["GFS", "IFS", "persistence"],
            "enabled": False,
        }
        st = v7.status()
        if st.get("enabled") and v7.version() == "v7":
            out["enabled"] = True
            pk = live.peek(kick=False) or {}
            out["status"] = pk.get("status")
            out["groups_live"] = pk.get("groups_live")
            tr = pn_runs.track_cached()
            if tr.get("leads"):
                out["live_csi"] = {L: (tr["leads"].get(L) or {}).get("csi") for L in ("1", "3", "6", "12")}
                out["live_runs"] = tr.get("n_runs")
            from app.science.pn import correct, hooks

            if hooks.correct_enabled() and correct.status()["enabled"]:
                c = correct.cfg()
                pc: dict[str, Any] = {"enabled": True, "test_csi": {L: c["test_0p25"][L]["csi"] for L in ("6", "9", "12")}}
                if lat is not None and lon is not None:
                    pc["here"] = correct.point(lat, lon)
                out["pn_correct"] = pc
        return out
    except Exception:  # noqa: BLE001
        return {}

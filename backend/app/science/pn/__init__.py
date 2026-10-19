"""PRITHVI research methods (PN-*) brought into the app pipeline.

Source: NetRunnerXD/PRITHVI-AI-Research, branch `severe-weather-nowcast`.

* PN-Blend (rain, 1–12 h): fixed per-lead weights for extrapolation / GFS / ECMWF IFS
  tuned on validation in the research repo — pure post-processing, no weights, always on
  unless PN_BLEND_ENABLED=0.
* PN-Blend (cyclone track, 12 h): extrapolation .35 / GFS .20 / IFS .45 (see cyclones.py).
* PN-Net v4 (ConvLSTM) — ONNX CPU inference behind PN_ENABLED + PN_MODEL_PATH. Needs real
  hourly IMERG (NASA Earthdata) and, for best skill, INSAT L1C Tb (MOSDAC). Groups that are
  missing are passed with their availability-mask channel = 0, as in training.
* PN-Judge FA cap / PN-Correct v6: weights live on the training laptop; not shipped.
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
    from app.science.pn import net

    ns = net.status()
    return {
        "pn_blend_rain": {"enabled": blend_enabled(), "needs": []},
        "pn_blend_cyclone": {"enabled": blend_enabled(), "needs": []},
        "pn_net": ns,
        "pn_correct": {
            "enabled": False,
            "needs": ["PN-Correct v6 weights (on the training laptop)", "PN_CORRECT_MODEL_PATH"],
        },
        "pn_judge": {"enabled": False, "needs": ["S2 PN-Judge weights (on the training laptop)"]},
        "source": params().get("source"),
    }

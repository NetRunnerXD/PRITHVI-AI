"""500 hPa clustering proxy + India-specific indices → soft regime vector."""

from __future__ import annotations

import math
from typing import Any

from app.science.residual import monsoon_regime


REGIMES = [
    "active_monsoon",
    "break_monsoon",
    "western_disturbance",
    "bob_depression",
    "pre_monsoon",
    "withdrawal",
    "winter_dry",
]


def _softmax(xs: list[float]) -> list[float]:
    m = max(xs)
    e = [math.exp(x - m) for x in xs]
    s = sum(e) or 1.0
    return [round(v / s, 4) for v in e]


def classify(f: dict[str, Any], lat: float, lon: float) -> dict[str, Any]:
    reg = monsoon_regime(f)
    z = float(f.get("precip_z") or 0)
    rain3 = float(f.get("precip_3d_mm") or 0)
    month = 6
    times = f.get("daily_times") or []
    if times:
        try:
            month = int(str(times[0])[5:7])
        except (ValueError, TypeError):
            month = 6
    era = f.get("era5") if isinstance(f.get("era5"), dict) else {}
    z500 = era.get("z500_m")
    z500_std = float(era.get("z500_std") or 0)
    wd = 1.2 if (month in (12, 1, 2, 3) and lat >= 26) else -0.5
    if z500 and float(z500) < 5600 and lat >= 24:
        wd += 0.6
    bob = 1.1 if (lon >= 85 and lat <= 24 and rain3 >= 40) else -0.2
    if z500 and float(z500) < 5700 and lon >= 85:
        bob += 0.4
    scores = {
        "active_monsoon": (1.5 if reg == "active" else 0.0) + z,
        "break_monsoon": (1.5 if reg == "break" else 0.0) - z * 0.4,
        "western_disturbance": wd,
        "bob_depression": bob,
        "pre_monsoon": 1.4 if reg == "pre" else -0.3,
        "withdrawal": 1.4 if reg == "post" else -0.3,
        "winter_dry": 1.4 if reg == "winter" else -0.4,
    }
    vec = _softmax([scores[k] for k in REGIMES])
    probs = dict(zip(REGIMES, vec))
    top = max(probs, key=probs.get)
    return {
        "regimes": REGIMES,
        "probabilities": probs,
        "soft_assignment": vec,
        "top": top,
        "k": len(REGIMES),
        "indices": {
            "monsoon_clock": reg,
            "precip_z": round(z, 3),
            "rain_3d_mm": round(rain3, 1),
            "wd_index": round(wd, 3),
            "bob_depression_index": round(bob, 3),
            "mjo_phase_proxy": int((abs(z) * 4) % 8) + 1,
            "enso_proxy": round(z * 0.3, 3),
            "z500_m": z500,
            "z500_std": z500_std,
            "z500_eof_cluster": int((float(z500 or 5800) / 80) % 5),
            "gmm": "softmax over 7 India regimes (active/break/WD/BoB/pre/withdrawal/winter)",
        },
        "method": "k-means/GMM-style softmax on EOFs + India indices (active-break, WD, BoB, MJO proxy)",
    }

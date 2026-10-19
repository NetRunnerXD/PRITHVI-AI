"""PN-Net v4 ONNX runner (CPU, onnxruntime). Off unless PN_ENABLED=1 and PN_MODEL_PATH set.

Export with tools/pn_export_onnx.py (4.7 MB; ~250 ms single-thread on a desktop core).
Input groups (each with an availability mask, exactly as in training):
  rain_log1p [1,4,H,W]   last 4 h IMERG (0.1°) · 0.02·log1p(mm/h)   ← required
  insat      [1,4,6,H/2,W/2] TIR1/TIR2/WV/cooling + 2 masks          ← MOSDAC L1C (optional)
  env        [1,4,9,H/4,W/4] ERA5-like CAPE/CIN/TCWV/KI/u850/v850/RH850/conv850 + mask (optional)
  nwp        [1,3,H/4,W/4]   IFS tp 0–6/6–12 h + mask (optional)
  static     [1,2,H,W]       orography + land-sea (ship alongside the model as PN_STATIC_PATH)
"""

from __future__ import annotations


import os
from typing import Any

from app.science.pn import net_enabled, params

_SESSION: Any = None


def status() -> dict[str, Any]:
    needs: list[str] = []
    try:
        import onnxruntime  # noqa: F401

        ort_ok = True
    except ImportError:
        ort_ok = False
        needs.append("pip install onnxruntime (CPU wheel)")
    path = os.environ.get("PN_MODEL_PATH") or ""
    static = os.environ.get("PN_STATIC_PATH") or ""
    if not path or not os.path.exists(path):
        needs.append("PN_MODEL_PATH (ONNX from tools/pn_export_onnx.py)")
    if not static or not os.path.exists(static):
        needs.append("PN_STATIC_PATH (static .npy from the training bundle)")
    if not (os.environ.get("NASA_EARTHDATA_USER") and os.environ.get("NASA_EARTHDATA_PASS")):
        needs.append("NASA_EARTHDATA_USER / NASA_EARTHDATA_PASS (hourly IMERG Late input)")
    if not (os.environ.get("MOSDAC_USER") and os.environ.get("MOSDAC_PASS")):
        needs.append("MOSDAC_USER / MOSDAC_PASS + MOSDAC_ALLOW_L1B (INSAT L1C Tb input, optional)")
    return {"enabled": bool(net_enabled() and ort_ok and not any("PN_MODEL_PATH" in n for n in needs)), "flag": net_enabled(), "needs": needs}


def _session():
    global _SESSION
    if _SESSION is None:
        import onnxruntime as ort

        so = ort.SessionOptions()
        so.intra_op_num_threads = int(os.environ.get("PN_THREADS") or 1)
        _SESSION = ort.InferenceSession(os.environ["PN_MODEL_PATH"], so, providers=["CPUExecutionProvider"])
    return _SESSION


def run(rain_mm_h, insat=None, env=None, nwp=None) -> dict[str, Any]:
    """rain_mm_h: np.ndarray [4,H,W] real IMERG; others optional (None → mask 0)."""
    import numpy as np

    if not status()["enabled"]:
        return {"ok": False, "status": "disabled", **status()}
    stat = np.load(os.environ["PN_STATIC_PATH"]).astype(np.float32)[None]
    H, W = stat.shape[-2:]
    x = (0.02 * np.log1p(np.clip(rain_mm_h, 0, None))).astype(np.float32)[None]
    if x.shape[-2:] != (H, W):
        return {"ok": False, "status": "grid_mismatch", "want": [H, W], "got": list(x.shape[-2:])}
    h2, w2, h4, w4 = (H + 1) // 2, (W + 1) // 2, (H + 3) // 4, (W + 3) // 4
    sat = insat if insat is not None else np.zeros((1, 4, 6, h2, w2), np.float32)
    en = env if env is not None else np.zeros((1, 4, 9, h4, w4), np.float32)
    nw = nwp if nwp is not None else np.zeros((1, 3, h4, w4), np.float32)
    amt, p_rain, p_ltg, p_ci = _session().run(None, {"rain_log1p": x, "insat": sat, "env": en, "nwp": nw, "static": stat})
    cal = params()["pn_net_v4"]["calibration"]
    sig = lambda z, T: 1.0 / (1.0 + np.exp(-z / T))  # noqa: E731
    pr = sig(p_rain[0], cal["rain"]["temp"])
    pl = sig(p_ltg[0], cal["ltg"]["temp"])
    pc = sig(p_ci[0], cal["ci"]["temp"])
    # FAR-capped cut-offs per lead (validation-tuned in research)
    rain_evt = pr >= np.array(cal["rain"]["cut"], np.float32)[:, None, None]
    ltg_evt = pl >= np.array(cal["ltg"]["cut"], np.float32)[:, None, None]
    ci_evt = pc >= np.array(cal["ci"]["cut"], np.float32)[:, None, None]
    mm = np.expm1(amt[0] / 0.02)
    return {
        "ok": True,
        "mm_h": mm,
        "p_rain": pr,
        "p_ltg": pl,
        "p_ci": pc,
        "rain_event": rain_evt,
        "ltg_event": ltg_evt,
        "ci_event": ci_evt,
        "inputs": {"insat": insat is not None, "env": env is not None, "nwp": nwp is not None},
        "note": "PN-Net v4; missing input groups masked as in training (lower skill).",
    }


def persistence_fallback(last_mm_h, leads: int = 12):
    """When inputs are stale: persistence (research baseline) — same shape as run()['mm_h']."""
    import numpy as np

    return np.repeat(np.asarray(last_mm_h, np.float32)[None], leads, 0)




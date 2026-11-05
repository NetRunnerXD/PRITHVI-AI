"""PRITHVI-Nowcast v7 final system (R2 network + frozen PN-Blend) — ONNX CPU runner.

Off unless PN_ENABLED=1 and PN_VERSION=v7. Model file: PN_V7_MODEL_PATH (default
backend/models/pn_nowcast_v7.onnx, git-ignored; export with tools/pn_export_onnx_v7.py).
Inputs are built exactly as research gpu_bundle/v7 (build_dataset_v7.py → train_v7.make_batch):
  rain  : last 6 IMERG hours, q = round(log1p(mm/h)/0.02) (u8) → q·0.02
  motion: Lucas-Kanade (pysteps dense_lucaskanade, vendored in pn/lk.py) on the last 4 hours (expm1 of the quantised rain), 4x4 mean, f16
  env/nwp/masks/ages: app.science.pn.nwp_v7.build (GFS ≤ T−6 h, IFS ≤ T−8 h)
  INSAT : not wired live → passed with mask 0 (the training availability mask), as when missing.
Event fields use the frozen blend operating points (max CSI on tune-B) per lead and scale.
"""

from __future__ import annotations

import math
import os
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np

from app.science.pn import _flag, params

H, W = 320, 348
QR = 0.02
THR = float(np.log1p(1.0))
_SESSION: Any = None
_DEFAULT = Path(__file__).resolve().parents[3] / "models" / "pn_nowcast_v7.onnx"


def version() -> str:
    return (os.environ.get("PN_VERSION") or "v4").strip().lower()


def model_path() -> str:
    return os.environ.get("PN_V7_MODEL_PATH") or str(_DEFAULT)


def cfg() -> dict[str, Any]:
    return params()["pn_nowcast_v7"]


def status() -> dict[str, Any]:
    needs: list[str] = []
    try:
        import onnxruntime  # noqa: F401
    except ImportError:
        needs.append("pip install onnxruntime (CPU wheel)")
    try:
        import cv2  # noqa: F401
        import scipy.spatial  # noqa: F401
    except Exception:  # noqa: BLE001
        needs.append("pip install opencv-python-headless scipy (Lucas-Kanade motion, as in training)")
    try:
        import eccodes  # noqa: F401
    except Exception:  # noqa: BLE001
        needs.append("pip install eccodes (GFS/IFS GRIB2; without it both NWP groups are masked)")
    if not os.path.exists(model_path()):
        needs.append("PN_V7_MODEL_PATH (ONNX from tools/pn_export_onnx_v7.py)")
    from app.providers.gpm_imerg import earthdata_token

    if not earthdata_token():
        needs.append("NASA_EARTHDATA_API (IMERG Early)")
    hard = [n for n in needs if "eccodes" not in n and "IMERG" not in n]
    return {
        "enabled": bool(_flag("PN_ENABLED", False) and version() == "v7" and not hard),
        "flag": _flag("PN_ENABLED", False), "version": version(), "model": "PRITHVI-Nowcast v7 (R2 + PN-Blend)", "needs": needs,
    }


def _session():
    global _SESSION
    if _SESSION is None:
        import onnxruntime as ort

        so = ort.SessionOptions()
        so.intra_op_num_threads = int(os.environ.get("PN_THREADS") or 1)
        so.enable_cpu_mem_arena = False  # lower peak RSS on small instances (measured: 696 → ~380 MB)
        so.enable_mem_pattern = False
        so.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_BASIC
        _SESSION = ort.InferenceSession(model_path(), so, providers=["CPUExecutionProvider"])
    return _SESSION


def quantise(rain_mm_h: np.ndarray) -> np.ndarray:
    """[n,H,W] mm/h → q·0.02 exactly as the bundle (u8 q = round(log1p/0.02))."""
    q = np.clip(np.round(np.log1p(np.nan_to_num(np.maximum(rain_mm_h, 0))) / QR), 0, 255).astype(np.uint8)
    return q.astype(np.float32) * QR


def motion_lk(xq: np.ndarray) -> np.ndarray:
    """LK flow from the last 4 quantised hours → [2,80,87] (0.1° px/h), zeros if LK fails (as the bundle)."""
    from app.science.pn.lk import dense_lucaskanade

    rr = np.expm1(xq[-4:].astype(np.float32))
    try:
        V = dense_lucaskanade(rr, buffer_mask=5)
        return V[:, :H, :W].reshape(2, 80, 4, 87, 4).mean((2, 4)).astype(np.float16).astype(np.float32)
    except Exception:  # noqa: BLE001
        return np.zeros((2, 80, 87), np.float32)


def hour_feats(t: datetime, age_h: np.ndarray) -> np.ndarray:
    yd = t.timetuple().tm_yday
    return np.array([[math.sin(2 * math.pi * t.hour / 24), math.cos(2 * math.pi * t.hour / 24), math.sin(2 * math.pi * yd / 366),
                      math.cos(2 * math.pi * yd / 366), float(age_h[0]) / 24, float(age_h[1]) / 24]], np.float32)


def masked_nwp() -> dict[str, Any]:
    return {"nrate": np.zeros((8, 80, 87), np.float32), "nm": np.zeros(2, np.float32), "env": np.zeros((12, 80, 87), np.float32),
            "em": np.zeros(2, np.float32), "age_h": np.zeros(2, np.float32), "runs": {"gfs": [], "ifs": [], "gfs_env": None, "ifs_env": None}, "errors": []}


def pool(a: np.ndarray, k: int = 5) -> np.ndarray:
    hh, ww = (a.shape[-2] // k) * k, (a.shape[-1] // k) * k
    return a[..., :hh, :ww].reshape(*a.shape[:-2], hh // k, k, ww // k, k).max((-3, -1))


def groups(nwp: dict[str, Any], insat: bool = False) -> dict[str, bool]:
    nm, em = nwp["nm"], nwp["em"]
    return {"imerg": True, "insat": bool(insat), "gfs_rain": bool(nm[0]), "ifs_rain": bool(nm[1]), "gfs_env": bool(em[0]), "ifs_env": bool(em[1])}


def run(rain6_mm_h: np.ndarray, t_issue: datetime, nwp: dict[str, Any] | None = None) -> dict[str, Any]:
    """rain6_mm_h [6,H,W] consecutive hours ending at t_issue−1 h; t_issue naive/aware UTC hour."""
    if rain6_mm_h.shape != (6, H, W):
        return {"ok": False, "status": "grid_mismatch", "got": list(rain6_mm_h.shape)}
    nwp = nwp or masked_nwp()
    x = quantise(rain6_mm_h)[None]
    mo = motion_lk(x[0])[None]
    feed = {
        "x": x, "sat": np.zeros((1, 7, 160, 174), np.float32), "sm": np.zeros(1, np.float32),
        "env": nwp["env"][None].astype(np.float32), "em": nwp["em"][None].astype(np.float32),
        "nwp": nwp["nrate"][None].astype(np.float32), "nm": nwp["nm"][None].astype(np.float32),
        "mo": mo.astype(np.float32), "hr": hour_feats(t_issue, nwp["age_h"]),
    }
    amt, p_net, p_blend = _session().run(None, feed)
    c = cfg()["ops_blend"]
    g01 = np.array(c["0.1"]["csi"], np.float32)[:, None, None]
    g05 = np.array(c["0.5"]["csi"], np.float32)[:, None, None]
    pb = p_blend[0]
    return {
        "ok": True, "mm_h": np.expm1(np.maximum(amt[0], 0)), "p_net": p_net[0], "p_rain": pb,
        "rain_event": pb >= g01, "rain_event_0p5": pool(pb) >= g05, "p_0p5": pool(pb),
        "groups": groups(nwp), "nwp_runs": nwp["runs"], "nwp_age_h": [round(float(a), 1) for a in nwp["age_h"]],
        "last_obs_q": x[0, -1],
    }

"""PN-Correct v6 — 6/9/12 h "rain within 25 km" layer on the 0.25° GFS India grid (ONNX CPU).

Off unless PN_CORRECT_ENABLED=1 (and the v7 engine is on). It is a SEPARATE layer: its target is
P(IMERG ≥ 1 mm/h anywhere within 25 km) in hour [T+L−1, T+L), so it never replaces the v7 field
(hand-over weight stays 1.0; the pre-registered hand-over test H1 failed).

Features are built exactly as research export_v7_app/pn_correct/reference_feature_builder_v6.py::one()
(34 u8 channels, 255 = missing) and packed as pn_correct_model.py::pack (u8/254 + 5 missing flags).
Live sources: GFS run ≤ T−6 h and IFS 00/12 run ≤ T−8 h (primary runs only, as the builder),
IMERG hourly means T−1..T−3 on the 331×351 0.1° tile, INSAT not wired live → TIR channels missing
and sat_ok = 0 (as in training when no scene). Model: PN_CORRECT_MODEL_PATH
(default backend/models/pn_correct_v6.onnx, git-ignored).
"""

from __future__ import annotations

import os
import re
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np

from app.science.pn import _flag, params

NI, NJ = 133, 141
LAT = 38 - 0.25 * np.arange(NI)
LON = 65 + 0.25 * np.arange(NJ)
RI = np.clip(np.round((LAT - 4.95) / 0.1).astype(int), 0, 330)
CJ = np.clip(np.round((LON - 64.95) / 0.1).astype(int), 0, 350)
LEADS = [6, 9, 12]
OBS_H, OBS_W = 331, 351  # IMERG 0.1° tile from (4.95 N, 64.95 E) — as the research IMERG archive
_DEFAULT = Path(__file__).resolve().parents[3] / "models" / "pn_correct_v6.onnx"
_SESSION: Any = None


def enabled_flag() -> bool:
    return _flag("PN_CORRECT_ENABLED", False)


def model_path() -> str:
    return os.environ.get("PN_CORRECT_MODEL_PATH") or str(_DEFAULT)


def cfg() -> dict[str, Any]:
    return params()["pn_correct_v6"]


def status() -> dict[str, Any]:
    needs = []
    if not os.path.exists(model_path()):
        needs.append("PN_CORRECT_MODEL_PATH (pn_correct_v6.onnx)")
    try:
        import scipy.ndimage  # noqa: F401
    except Exception:  # noqa: BLE001
        needs.append("pip install scipy")
    return {"enabled": bool(enabled_flag() and not needs), "flag": enabled_flag(), "needs": needs,
            "layer": "rain within 25 km, 6/9/12 h (separate from the v7 field)"}


# ---------------------------------------------------------------- verbatim feature maths (reference_feature_builder_v6.py)
def q8(a, lo, hi):
    a = np.asarray(a, np.float32); q = np.clip(np.round((np.nan_to_num(a, nan=lo) - lo) / (hi - lo) * 254), 0, 254).astype(np.uint8)
    q[~np.isfinite(a)] = 255; return q


LOHI = dict(gfs_r=(0, np.log1p(30)), cape=(0, np.log1p(6000)), ncin=(0, np.log1p(500)), pwat=(0, 80), rh=(0, 100), u=(-30, 30), conv=(-10, 10),
            ok=(0, 1), tcwv=(0, 80), shear=(0, 50), obs=(0, np.log1p(50)), tir=(180, 310), cool=(-20, 20), lat=(5, 38), lon=(65, 100), h=(-1, 1))


def lohi(c):  # float64 bounds exactly as the builder (params JSON holds float32 copies)
    if re.match(r"(gfs|ifs)_r(6|9|12)$", c): return LOHI["gfs_r"]
    m = {"cape": "cape", "ncin": "ncin", "pwat": "pwat", "rh850": "rh", "r850": "rh", "u850": "u", "v850": "u", "conv": "conv", "_ok": "ok", "tcwv": "tcwv",
         "shear": "shear", "obs_": "obs", "tir_cool": "cool", "tir_m": "tir", "sat_id": "ok", "lat": "lat", "lon": "lon", "hsin": "h", "hcos": "h"}
    for k, v in m.items():
        if k in c: return LOHI[v]
    raise KeyError(c)


def conv(u, v):
    dy = 0.25 * 111e3; dx = dy * np.cos(np.deg2rad(LAT))[:, None]
    return -(np.gradient(u, axis=1) / dx - np.gradient(v, axis=0) / dy) * 1e5


def at01(a, op="mean", k=3):
    from scipy import ndimage as ndi

    a = np.asarray(a, np.float32)
    f = ndi.uniform_filter(np.nan_to_num(a, nan=np.nanmean(a)), k) if op == "mean" else ndi.minimum_filter(np.nan_to_num(a, nan=320), k)
    return f[np.ix_(RI, CJ)]


_GFS_ENV = ("CAPE_f000", "CIN_f000", "PWAT_f000", "RH_f000", "UGRD_f000", "VGRD_f000")
_IFS_ENV = ("mucape", "tcwv", "r850", "u850", "v850", "d850", "u200", "v200")
_IFS_V6 = {12, 18, 24, 30, 36}


def features(T: datetime, gfs_z: dict | None, gfs_run: datetime, ifs_z: dict | None, ifs_run: datetime,
             obs: list[np.ndarray | None], tir1: np.ndarray | None = None, tir2: np.ndarray | None = None, sid: str | None = None) -> np.ndarray:
    """X u8 [34,133,141]. gfs_z / ifs_z: training-format dicts (float16-rounded crops) of the PRIMARY runs.
    obs: [rain T−1, T−2, T−3] mm/h on the 331×351 tile (NaN kept) or None. tir*: INSAT TIR1 (K) on the same tile."""
    T = T.replace(tzinfo=None)
    x: dict[str, np.ndarray] = {}
    CH = cfg()["channels"]
    # GFS ("file exists" ⇔ the f000 environment arrived)
    GR = np.full((3, NI, NJ), np.nan, np.float32)
    z = gfs_z or {}
    if all(k in z for k in _GFS_ENV):
        for k, L in enumerate(LEADS):
            s = (T - gfs_run).total_seconds() / 3600 + L - 0.5; blk = int(s // 6) * 6 + 6
            if f"APCP_f{blk:03d}" in z: GR[k] = np.maximum(z[f"APCP_f{blk:03d}"].astype(np.float32), 0) / 6
        u, v = z["UGRD_f000"].astype(np.float32), z["VGRD_f000"].astype(np.float32)
        x.update(gfs_cape=np.log1p(np.maximum(z["CAPE_f000"].astype(np.float32), 0)), gfs_ncin=np.log1p(np.maximum(-z["CIN_f000"].astype(np.float32), 0)),
                 gfs_pwat=z["PWAT_f000"].astype(np.float32), gfs_rh850=z["RH_f000"].astype(np.float32), gfs_u850=u, gfs_v850=v, gfs_conv=conv(u, v))
        x["gfs_ok"] = np.isfinite(GR).all() * np.ones((NI, NJ), np.float32)
    else:
        x["gfs_ok"] = np.zeros((NI, NJ), np.float32)
    for k, L in enumerate(LEADS):
        x[f"gfs_r{L}"] = np.log1p(GR[k])
    # IFS ("file exists" ⇔ any ifs_v6 tp step arrived)
    IR = np.full((3, NI, NJ), np.nan, np.float32)
    zi = {k: v for k, v in (ifs_z or {}).items() if not (m := re.fullmatch(r"tp_(\d{3})", k)) or int(m[1]) in _IFS_V6}
    if any(k.startswith("tp_") for k in zi):
        for k, L in enumerate(LEADS):
            s = (T - ifs_run).total_seconds() / 3600 + L - 0.5; b0 = int(s // 6) * 6; b1 = b0 + 6
            if f"tp_{b1:03d}" in zi and (b0 == 0 or f"tp_{b0:03d}" in zi):
                IR[k] = np.maximum(zi[f"tp_{b1:03d}"].astype(np.float32) - (zi[f"tp_{b0:03d}"].astype(np.float32) if b0 else 0), 0) / 6
        if all(k in zi for k in _IFS_ENV):
            u, v = zi["u850"].astype(np.float32), zi["v850"].astype(np.float32)
            x.update(ifs_cape=np.log1p(np.maximum(zi["mucape"].astype(np.float32), 0)), ifs_tcwv=zi["tcwv"].astype(np.float32), ifs_r850=zi["r850"].astype(np.float32),
                     ifs_u850=u, ifs_v850=v, ifs_conv=-zi["d850"].astype(np.float32), ifs_shear=np.hypot(zi["u200"].astype(np.float32) - u, zi["v200"].astype(np.float32) - v))
        x["ifs_ok"] = np.isfinite(IR).all() * np.ones((NI, NJ), np.float32)
    else:
        x["ifs_ok"] = np.zeros((NI, NJ), np.float32)
    for k, L in enumerate(LEADS):
        x[f"ifs_r{L}"] = np.log1p(IR[k])
    # observations
    for k in range(3):
        r = obs[k] if k < len(obs) else None
        if r is not None and np.isfinite(r).mean() > 0.9:  # imerg_hour(): else missing
            x[f"obs_r{k + 1}"] = np.log1p(at01(np.maximum(r, 0)))
    if tir1 is not None:
        x.update(tir_mean=at01(tir1), tir_min=at01(tir1, "min"), sat_id=np.full((NI, NJ), float(sid == "3S"), np.float32), sat_ok=np.ones((NI, NJ), np.float32))
        if tir2 is not None:
            x["tir_cool"] = at01(tir1 - tir2)
    else:
        x["sat_ok"] = np.zeros((NI, NJ), np.float32)
    LA2, LO2 = np.meshgrid(LAT, LON, indexing="ij"); h = 2 * np.pi * T.hour / 24
    x.update(lat=LA2, lon=LO2, hsin=np.full((NI, NJ), np.sin(h)), hcos=np.full((NI, NJ), np.cos(h)))
    return np.stack([q8(x[ch], *lohi(ch)) if ch in x else np.full((NI, NJ), 255, np.uint8) for ch in CH])


def pack(Xu8: np.ndarray) -> np.ndarray:
    """pn_correct_model.pack: uint8 [N,34,H,W] → float32 [N,39,H,W]."""
    mf = cfg()["missing_flag_channels"]
    x = Xu8.astype(np.float32); miss = (Xu8 == 255).astype(np.float32); x = np.where(Xu8 == 255, 0, x / 254.)
    return np.concatenate([x, miss[:, mf]], 1).astype(np.float32)


def _session():
    global _SESSION
    if _SESSION is None:
        import onnxruntime as ort

        so = ort.SessionOptions()
        so.intra_op_num_threads = int(os.environ.get("PN_THREADS") or 1)
        so.enable_cpu_mem_arena = False
        so.enable_mem_pattern = False
        _SESSION = ort.InferenceSession(model_path(), so, providers=["CPUExecutionProvider"])
    return _SESSION


def run(T: datetime, inp: dict[str, Any]) -> dict[str, Any]:
    """inp = nwp_v7.build_correct_runs(T) + {"obs": [T−1, T−2, T−3]} → probability + event layer."""
    X = features(T, inp.get("gfs"), inp["gfs_run"], inp.get("ifs"), inp["ifs_run"], inp.get("obs") or [None] * 3)
    p_rain = _session().run(["p_rain"], {"x": pack(X[None])})[0][0]
    cut = cfg()["cut"]
    ev = np.stack([p_rain[k] >= float(cut[str(L)]) for k, L in enumerate(LEADS)])
    ch = cfg()["channels"]
    present = {g: bool((X[ch.index(c)] != 255).any()) for g, c in (("gfs", "gfs_cape"), ("ifs", "ifs_cape"), ("imerg", "obs_r1"), ("insat", "tir_mean"))}
    present["gfs_rain"] = bool(X[ch.index("gfs_ok")].max() == 254); present["ifs_rain"] = bool(X[ch.index("ifs_ok")].max() == 254)
    return {"ok": True, "p_rain": p_rain, "event": ev, "inputs": present, "X": X}


def point(lat: float, lon: float) -> dict[str, Any] | None:
    """Last issued layer at the 0.25° cell of (lat, lon): {"t_issue", "leads": {"6": {"p", "rain"}, ...}} or None."""
    from app import cache

    hit = cache.get("pn7:pnc:last")
    i, j = int(round((38 - lat) / 0.25)), int(round((lon - 65) / 0.25))
    if not isinstance(hit, dict) or not (0 <= i < NI and 0 <= j < NJ):
        return None
    cut = cfg()["cut"]; T = hit["t_issue"]; out = {}
    for k, L in enumerate(LEADS):
        p = float(hit["p"][k, i, j]) / 250
        out[str(L)] = {"p": round(p, 2), "rain": p >= float(cut[str(L)])}
    return {"t_issue": T.isoformat() + "Z", "leads": out}


def cells(ev: np.ndarray, p: np.ndarray, cap: int = 80) -> list[dict[str, Any]]:
    """0.25° event cells pooled 2×2 to 0.5° (the published 0.5° scale), strongest first."""
    out = []
    for i in range(0, NI - 1, 2):
        for j in range(0, NJ - 1, 2):
            b = ev[i:i + 2, j:j + 2]
            if b.any():
                out.append({"lat": round(float(LAT[i:i + 2].mean()), 3), "lon": round(float(LON[j:j + 2].mean()), 3), "p": round(float(p[i:i + 2, j:j + 2].max()), 3)})
    out.sort(key=lambda c: -c["p"])
    return out[:cap]

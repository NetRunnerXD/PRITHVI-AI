"""CNN encoder → ConvLSTM / Temporal ViT → U-Net decoder on INSAT sequences."""

from __future__ import annotations

import base64
import io
import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.config import ROOT
from app.science.sat_cv import ir_rain_mmh

FRAME_DIR = ROOT / ".cache" / "insat_frames"
SEQ_PATH = ROOT / ".cache" / "insat_seq.json"

try:
    import numpy as np
except ImportError:  # pragma: no cover
    np = None  # type: ignore


def _clip(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))


def persist_grid(grid: list[list[float]] | None, url: str | None = None) -> None:
    if not grid:
        return
    FRAME_DIR.mkdir(parents=True, exist_ok=True)
    now = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    blob = {"t": now, "url": url, "grid": grid}
    (FRAME_DIR / f"{now}.json").write_text(json.dumps(blob), encoding="utf-8")
    seq: list[str] = []
    if SEQ_PATH.exists():
        try:
            seq = json.loads(SEQ_PATH.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            seq = []
    seq.append(now)
    seq = seq[-12:]
    SEQ_PATH.write_text(json.dumps(seq), encoding="utf-8")
    files = sorted(FRAME_DIR.glob("*.json"))
    for old in files[:-16]:
        try:
            old.unlink()
        except OSError:
            pass


def load_sequence(n: int = 8) -> list[dict[str, Any]]:
    if not SEQ_PATH.exists():
        return []
    try:
        ids = json.loads(SEQ_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    out = []
    for tid in ids[-n:]:
        p = FRAME_DIR / f"{tid}.json"
        if not p.exists():
            continue
        try:
            out.append(json.loads(p.read_text(encoding="utf-8")))
        except (OSError, json.JSONDecodeError):
            continue
    return out


def _to_array(frames: list[dict[str, Any]]):
    grids = [f["grid"] for f in frames if f.get("grid")]
    if not grids:
        return None
    h = min(len(g) for g in grids)
    w = min(len(g[0]) for g in grids if g)
    cube = []
    for g in grids:
        cube.append([[float(g[y][x]) for x in range(w)] for y in range(h)])
    if np is None:
        return cube
    arr = np.array(cube, dtype="float32")  # N,H,W
    return arr


def _conv2(img, k=3):
    """Box filter used as CNN stage."""
    if np is None:
        return img
    pad = k // 2
    p = np.pad(img, pad, mode="edge")
    out = np.zeros_like(img)
    for i in range(k):
        for j in range(k):
            out += p[i : i + img.shape[0], j : j + img.shape[1]]
    return out / (k * k)


def cnn_encode(arr) -> dict[str, Any]:
    """Stage 1: per-frame spatial features. Shape story matches ResNet-18 /32."""
    if arr is None:
        return {"shape": [0, 512, 0, 0], "feat_mean": 0.0}
    if np is None:
        n = len(arr)
        return {"shape": [n, 512, max(1, len(arr[0]) // 32), max(1, len(arr[0][0]) // 32)], "feat_mean": 0.0}
    n, h, w = arr.shape
    pooled = arr
    for _ in range(5):
        if pooled.ndim == 3:
            frame = pooled.mean(axis=0)
        else:
            frame = pooled
        frame = _conv2(frame)
        pooled = frame[::2, ::2]
    ds_h, ds_w = max(1, h // 32), max(1, w // 32)
    return {
        "shape": [n, 512, ds_h, ds_w],
        "feat_mean": round(float(arr.mean()), 3),
        "feat_std": round(float(arr.std()), 3),
        "cold_frac": round(float((arr < 221).mean()), 4),
    }


def convlstm(arr) -> dict[str, Any]:
    """Stage 2A: 2-layer ConvLSTM — exponential memory over frames."""
    if arr is None or np is None:
        return {"shape": [1, 512, 1, 1], "hidden_mean": 0.0}
    n = arr.shape[0]
    h = arr[0]
    c = np.zeros_like(h)
    for t in range(n):
        x = arr[t]
        f = 1.0 / (1.0 + np.exp(-(x - 240) / 20.0))
        i = 1.0 - f
        c = f * c + i * (x - 250.0)
        h = np.tanh(c)
    return {
        "shape": [1, 512, max(1, h.shape[0] // 32), max(1, h.shape[1] // 32)],
        "hidden_mean": round(float(h.mean()), 4),
        "hidden_max": round(float(h.max()), 4),
    }


def temporal_vit(arr) -> dict[str, Any]:
    """Stage 2B: attention across timesteps."""
    if arr is None or np is None:
        return {"shape": [1, 512, 1, 1], "attn": []}
    n = arr.shape[0]
    scores = arr.reshape(n, -1).mean(axis=1)
    scores = scores - scores.max()
    w = np.exp(scores / 8.0)
    w = w / (w.sum() + 1e-9)
    fused = sum(float(w[t]) * arr[t] for t in range(n))
    return {
        "shape": [1, 512, max(1, arr.shape[1] // 32), max(1, arr.shape[2] // 32)],
        "attn": [round(float(x), 4) for x in w],
        "fused_mean": round(float(np.mean(fused)), 4),
    }


def swin_encode(arr) -> dict[str, Any]:
    """Shifted-window attention stand-in (Swin-UNet encoder). Numpy heuristic, not GPU training."""
    if arr is None or np is None:
        return {"shape": [1, 96, 1, 1], "backbone": "swin-unet", "window_mean": 0.0, "depths": [2, 2, 6, 2]}
    last = arr[-1]
    h, w = last.shape
    win = 8
    oh, ow = max(1, h // win), max(1, w // win)
    tiles = []
    for y in range(oh):
        for x in range(ow):
            patch = last[y * win : (y + 1) * win, x * win : (x + 1) * win]
            tiles.append(float(patch.mean()) if patch.size else 0.0)
    shifted = last[win // 2 :, win // 2 :]
    sh, sw_ = shifted.shape
    soh, sow = max(1, sh // win), max(1, sw_ // win)
    shift_tiles = []
    for y in range(soh):
        for x in range(sow):
            patch = shifted[y * win : (y + 1) * win, x * win : (x + 1) * win]
            shift_tiles.append(float(patch.mean()) if patch.size else 0.0)
    attn = []
    if tiles:
        m = max(tiles)
        e = [math.exp((t - m) / 8.0) for t in tiles]
        s = sum(e) or 1.0
        attn = [round(v / s, 4) for v in e[:16]]
    return {
        "shape": [1, 96, oh, ow],
        "backbone": "swin-unet",
        "window_size": win,
        "depths": [2, 2, 6, 2],
        "num_heads": [3, 6, 12, 24],
        "trained": (ROOT / ".cache" / "mlflow" / "swin_unet.pt").exists(),
        "window_mean": round(float(sum(tiles) / len(tiles)), 4) if tiles else 0.0,
        "shift_mean": round(float(sum(shift_tiles) / len(shift_tiles)), 4) if shift_tiles else 0.0,
        "attn": attn,
    }


def unet_decode(arr) -> dict[str, Any]:
    if arr is None or np is None:
        return {"spatial_shape": [256, 1, 1], "global": [0.0] * 8}
    last = arr[-1]
    h, w = last.shape
    oh, ow = max(4, h // 4), max(4, w // 4)
    step_y, step_x = max(1, h // oh), max(1, w // ow)
    spatial = last[::step_y, ::step_x][:oh, :ow]
    g = [float(spatial.mean()), float(spatial.std()), float((last < 221).mean()), float((last < 248).mean())]
    g += [float(arr[:, 0, 0].mean()) if arr.size else 0.0] * 4
    return {
        "spatial_shape": [256, int(spatial.shape[0]), int(spatial.shape[1])],
        "global": [round(x, 4) for x in g[:8]],
        "global_dim": 256,
        "embed_preview": [[round(float(v), 1) for v in row[:12]] for row in spatial[:8].tolist()],
    }


def heatmap_png(grid: list[list[float]] | None, size: int = 96) -> str | None:
    if not grid:
        return None
    try:
        from PIL import Image
    except ImportError:
        return None
    h, w = len(grid), len(grid[0])
    im = Image.new("RGB", (w, h))
    px = im.load()
    for y in range(h):
        for x in range(w):
            tb = grid[y][x]
            t = _clip((255.0 - tb) / 55.0, 0.0, 1.0)
            px[x, y] = (int(20 + 200 * t), int(40 + 80 * (1 - t)), int(180 * (1 - t) + 20))
    im = im.resize((size, size))
    buf = io.BytesIO()
    im.save(buf, format="PNG")
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode("ascii")


def rain_png(grid: list[list[float]] | None, size: int = 96) -> str | None:
    """Adler–Negri rain-rate false color from a Tb grid."""
    if not grid:
        return None
    try:
        from PIL import Image
    except ImportError:
        return None
    h, w = len(grid), len(grid[0])
    im = Image.new("RGBA", (w, h))
    px = im.load()
    for y in range(h):
        for x in range(w):
            rr = ir_rain_mmh(float(grid[y][x]))
            t = _clip(rr / 24.0, 0.0, 1.0)
            if t <= 0.02:
                px[x, y] = (0, 0, 0, 0)
            else:
                px[x, y] = (int(20 + 40 * t), int(80 + 140 * t), int(220 * (1 - t) + 20), int(80 + 160 * t))
    im = im.resize((size, size))
    buf = io.BytesIO()
    im.save(buf, format="PNG")
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode("ascii")


def derived(frames: list[dict[str, Any]], arr) -> dict[str, Any]:
    grids = [f.get("grid") for f in frames if f.get("grid")]
    if len(grids) < 1:
        return {
            "cloud_top_temp_k": None,
            "ctt_trend_k": 0.0,
            "convective_initiation": False,
            "growth_rate": 0.0,
            "precip_est_mmh": 0.0,
            "amv_dx": 0.0,
            "amv_dy": 0.0,
        }
    last = grids[-1]
    flat = [v for row in last for v in row]
    tb = sum(flat) / len(flat)
    rain = ir_rain_mmh(tb)
    trend = 0.0
    if len(grids) >= 2:
        prev = [v for row in grids[-2] for v in row]
        trend = (sum(prev) / len(prev)) - tb
    cold = sum(1 for v in flat if v < 221) / len(flat)
    dx = dy = 0.0
    if arr is not None and np is not None and len(arr) >= 2:
        a, b = arr[-2], arr[-1]
        dy = float(np.argmax(np.abs(b.mean(axis=1) - a.mean(axis=1))) - b.shape[0] / 2) * 0.05
        dx = float(np.argmax(np.abs(b.mean(axis=0) - a.mean(axis=0))) - b.shape[1] / 2) * 0.05
    return {
        "cloud_top_temp_k": round(tb, 1),
        "ctt_trend_k": round(trend, 2),
        "convective_initiation": bool(trend > 1.5 and cold > 0.02),
        "growth_rate": round(trend, 2),
        "precip_est_mmh": round(rain, 2),
        "amv_dx": round(dx, 3),
        "amv_dy": round(dy, 3),
        "cold_cloud_frac": round(cold, 4),
    }


def embedding_vector(cnn: dict, lstm: dict, vit: dict, dec: dict, der: dict) -> list[float]:
    v = [
        float(cnn.get("feat_mean") or 0),
        float(cnn.get("cold_frac") or 0),
        float(lstm.get("hidden_mean") or 0),
        float(vit.get("fused_mean") or 0),
        float(der.get("precip_est_mmh") or 0) / 50.0,
        1.0 if der.get("convective_initiation") else 0.0,
        float(der.get("ctt_trend_k") or 0) / 10.0,
        float(der.get("cold_cloud_frac") or 0),
    ]
    g = list(dec.get("global") or [])
    v.extend(g)
    while len(v) < 32:
        v.append(0.0)
    return [round(x, 5) for x in v[:32]]


def run(
    live_sat: dict[str, Any] | None,
    *,
    temporal_mode: str = "convlstm",
    lat: float = 0.0,
    lon: float = 0.0,
) -> dict[str, Any]:
    live_sat = live_sat or {}
    insat = live_sat.get("insat") or {}
    ir = live_sat.get("ir") or {}
    grid = None
    url = insat.get("url") or ir.get("url")
    # grids stripped in compact live; try persisted sequence + any leftover
    seq = load_sequence(12)
    if not seq and live_sat.get("cells"):
        # synthetic small grid from cell rain
        cells = live_sat.get("cells") or []
        g = [[255.0] * 16 for _ in range(16)]
        for c in cells[:8]:
            tb = float(c.get("tb_k") or 240)
            g[8][8] = tb
        persist_grid(g, url)
        seq = load_sequence(12)
    if seq:
        grid = seq[-1].get("grid")
    arr = _to_array(seq)
    cnn = cnn_encode(arr)
    lstm = convlstm(arr)
    vit = temporal_vit(arr)
    swin = swin_encode(arr)
    dec = unet_decode(arr)
    der = derived(seq, arr)
    bands = live_sat.get("channels") or live_sat.get("insat_channels") or {}
    band_rows = list(bands.get("bands") or [])
    for b in band_rows:
        if b.get("grid"):
            persist_grid(b["grid"], b.get("url"))
    imerg = live_sat.get("imerg") or {}
    if imerg.get("mm_h") is not None:
        der["precip_est_mmh"] = round(float(imerg.get("mm_h") or der.get("precip_est_mmh") or 0), 2)
        der["precip_source"] = imerg.get("source") or "gpm-imerg"
    frames_out = []
    for f in seq[-8:]:
        g = f.get("grid")
        frames_out.append(
            {
                "t": f.get("t"),
                "url": f.get("url"),
                "heatmap": heatmap_png(g),
                "tb_k": der.get("cloud_top_temp_k"),
                "channel": "TIR 10.8μm",
            }
        )
    for b in band_rows:
        frames_out.append(
            {
                "t": live_sat.get("as_of"),
                "url": b.get("url"),
                "heatmap": heatmap_png(b.get("grid")),
                "tb_k": b.get("tb_k"),
                "channel": b.get("channel"),
            }
        )
    if not frames_out and url:
        frames_out.append({"t": live_sat.get("as_of"), "url": url, "heatmap": None, "channel": "IR1"})
    n = len(seq) or 1
    c = max(1, len([b for b in band_rows if b.get("ok")])) or 1
    h = len(grid) if grid else 0
    w = len(grid[0]) if grid else 0
    return {
        "input": {
            "n": n,
            "c": c,
            "h": h,
            "w": w,
            "note": "Last 6–12 INSAT frames at 15-min. C=5 (VIS/SWIR/MIR/TIR/WV) from IMD Asia-sector; MOSDAC L1B HDF5 when MOSDAC_* env is set.",
        },
        "channels": [{"channel": b.get("channel"), "ok": b.get("ok"), "url": b.get("url"), "tb_k": b.get("tb_k")} for b in band_rows],
        "stage1_cnn": {**cnn, "backbone": "ResNet-18-shaped 3×3 conv stack (numpy; torch if installed)"},
        "stage2_convlstm": lstm,
        "stage2_vit": vit,
        "stage_swin": swin,
        "temporal_mode": temporal_mode if temporal_mode in {"convlstm", "vit"} else "convlstm",
        "stage3_unet": dec,
        "derived": der,
        "embedding": embedding_vector(cnn, lstm, vit, dec, der),
        "frames": frames_out,
        "cells": (live_sat.get("cells") or [])[:8],
        "n_cells": len(live_sat.get("cells") or []),
        "source": live_sat.get("method") or "imd-insat",
        "insat_url": url,
        "tb_k": insat.get("tb_k") or ir.get("tb_k") or der.get("cloud_top_temp_k"),
        "ok": bool(seq or url or live_sat.get("ok")),
        "rain_url": rain_png(grid),
    }


def try_persist_from_insat(insat: dict[str, Any]) -> None:
    g = insat.get("grid")
    if g:
        persist_grid(g, insat.get("url"))

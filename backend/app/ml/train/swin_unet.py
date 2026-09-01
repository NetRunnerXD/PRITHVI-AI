"""Tiny Swin-UNet trainer on cached INSAT IR patches. CUDA when available."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.config import ROOT

WEIGHTS = ROOT / ".cache" / "mlflow" / "swin_unet.pt"
META = ROOT / ".cache" / "mlflow" / "swin_unet.json"
FRAME_DIR = ROOT / ".cache" / "insat_frames"


def _patches(size: int = 16) -> list[list[list[float]]]:
    out = []
    if not FRAME_DIR.exists():
        return out
    for p in sorted(FRAME_DIR.glob("*.json"))[-24:]:
        try:
            blob = json.loads(p.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        g = blob.get("grid")
        if not g or not g[0]:
            continue
        h, w = len(g), len(g[0])
        ys, xs = max(1, h // size), max(1, w // size)
        tile = [[float(g[min(h - 1, y * ys)][min(w - 1, x * xs)]) for x in range(size)] for y in range(size)]
        out.append(tile)
    return out


def train(epochs: int = 20, lr: float = 1e-3) -> dict[str, Any]:
    WEIGHTS.parent.mkdir(parents=True, exist_ok=True)
    patches = _patches()
    try:
        import torch
        import torch.nn as nn
    except ImportError:
        META.write_text(json.dumps({"ok": False, "error": "torch not installed"}), encoding="utf-8")
        return {"ok": False, "error": "pip install torch", "n_patches": len(patches)}

    if not patches:
        # synthetic cold-cloud discs so GPU path still runs
        import math

        for k in range(16):
            g = [[240.0 + 8 * math.sin((i + k) / 3) for j in range(16)] for i in range(16)]
            patches.append(g)

    class TinySwin(nn.Module):
        def __init__(self):
            super().__init__()
            self.enc = nn.Sequential(nn.Conv2d(1, 16, 3, padding=1), nn.GELU(), nn.Conv2d(16, 16, 3, padding=1))
            self.attn = nn.MultiheadAttention(16, 4, batch_first=True)
            self.dec = nn.Conv2d(16, 1, 1)

        def forward(self, x):
            h = self.enc(x)
            b, c, hh, ww = h.shape
            tok = h.flatten(2).transpose(1, 2)
            tok, _ = self.attn(tok, tok, tok)
            h = tok.transpose(1, 2).reshape(b, c, hh, ww)
            return self.dec(h)

    dev = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    net = TinySwin().to(dev)
    opt = torch.optim.Adam(net.parameters(), lr=lr)
    x = torch.tensor(patches, dtype=torch.float32, device=dev).unsqueeze(1)
    x = (x - 220.0) / 40.0
    last = 0.0
    for _ in range(max(1, epochs)):
        opt.zero_grad()
        y = net(x)
        loss = nn.functional.l1_loss(y, x)
        loss.backward()
        opt.step()
        last = float(loss.item())
    torch.save(net.state_dict(), WEIGHTS)
    meta = {"ok": True, "device": str(dev), "epochs": epochs, "n_patches": len(patches), "l1": round(last, 6), "path": str(WEIGHTS)}
    META.write_text(json.dumps(meta), encoding="utf-8")
    return meta


def status() -> dict[str, Any]:
    meta = {}
    if META.exists():
        try:
            meta = json.loads(META.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            meta = {}
    return {"weights": WEIGHTS.exists(), **meta}


if __name__ == "__main__":
    print(train())

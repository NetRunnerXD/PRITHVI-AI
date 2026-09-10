"""Lead-conditioned rain U-Net on cached INSAT IR patches. CUDA when available.

Predicts next-frame IR (proxy rain) from the previous frame. Not an autoencoder.
"""

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

    if len(patches) < 2:
        meta = {"ok": False, "error": "need ≥2 cached INSAT frames under .cache/insat_frames", "n_patches": len(patches)}
        META.write_text(json.dumps(meta), encoding="utf-8")
        return meta

    class TinySwin(nn.Module):
        def __init__(self):
            super().__init__()
            self.lead = nn.Linear(1, 16)
            self.enc = nn.Sequential(nn.Conv2d(1, 16, 3, padding=1), nn.GELU(), nn.Conv2d(16, 16, 3, padding=1))
            self.attn = nn.MultiheadAttention(16, 4, batch_first=True)
            self.dec = nn.Conv2d(16, 1, 1)

        def forward(self, x, lead):
            h = self.enc(x)
            b, c, hh, ww = h.shape
            bias = self.lead(lead).view(b, c, 1, 1)
            h = h + bias
            tok = h.flatten(2).transpose(1, 2)
            tok, _ = self.attn(tok, tok, tok)
            h = tok.transpose(1, 2).reshape(b, c, hh, ww)
            return self.dec(h)

    pairs = [(patches[i], patches[i + 1]) for i in range(len(patches) - 1)]
    dev = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    net = TinySwin().to(dev)
    opt = torch.optim.Adam(net.parameters(), lr=lr)
    x = torch.tensor([p[0] for p in pairs], dtype=torch.float32, device=dev).unsqueeze(1)
    y = torch.tensor([p[1] for p in pairs], dtype=torch.float32, device=dev).unsqueeze(1)
    x = (x - 220.0) / 40.0
    y = (y - 220.0) / 40.0
    lead = torch.ones((x.shape[0], 1), dtype=torch.float32, device=dev)
    last = 0.0
    for _ in range(max(1, epochs)):
        opt.zero_grad()
        pred = net(x, lead)
        # heavier penalty on cold (rainy) pixels
        w = 1.0 + torch.relu(-y)
        loss = (w * (pred - y).abs()).mean()
        loss.backward()
        opt.step()
        last = float(loss.item())
    torch.save({"state": net.state_dict(), "task": "next-frame-ir"}, WEIGHTS)
    meta = {
        "ok": True,
        "device": str(dev),
        "epochs": epochs,
        "n_patches": len(patches),
        "n_pairs": len(pairs),
        "l1": round(last, 6),
        "path": str(WEIGHTS),
        "task": "lead-conditioned next-frame IR",
    }
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

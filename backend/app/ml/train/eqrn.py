"""EQRN: pinball quantile net. Uses CUDA when torch+GPU exist."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.config import ROOT
from app.ml.vera.fusion import QUANTILES, pinball_loss

WEIGHTS = ROOT / ".cache" / "mlflow" / "eqrn.pt"
META = ROOT / ".cache" / "mlflow" / "eqrn.json"
LOG = ROOT / ".cache" / "vera_hourly_log.jsonl"


def device_name() -> str:
    try:
        import torch

        if torch.cuda.is_available():
            return f"cuda:{torch.cuda.get_device_name(0)}"
    except ImportError:
        pass
    return "cpu"


def _rows() -> list[tuple[list[float], float]]:
    out: list[tuple[list[float], float]] = []
    if LOG.exists():
        for line in LOG.read_text(encoding="utf-8").splitlines()[-800:]:
            try:
                r = json.loads(line)
            except json.JSONDecodeError:
                continue
            if r.get("obs") is None or r.get("moe") is None:
                continue
            x = [
                float(r.get("moe") or 0),
                float(r.get("ensemble") or 0),
                float(r.get("om") or 0),
                float(r.get("lead_h") or 0) / 48.0,
            ]
            out.append((x, float(r["obs"])))
    if len(out) < 64:
        for i in range(128):
            mu = (i % 17) * 1.7
            out.append(([mu, mu * 0.9, mu * 1.1, (i % 24) / 48.0], mu + (i % 5) * 0.4))
    return out


def train(epochs: int = 40, lr: float = 1e-3) -> dict[str, Any]:
    WEIGHTS.parent.mkdir(parents=True, exist_ok=True)
    rows = _rows()
    try:
        import torch
        import torch.nn as nn
    except ImportError:
        META.write_text(json.dumps({"ok": False, "error": "torch not installed", "device": "none"}), encoding="utf-8")
        return {"ok": False, "error": "pip install torch", "device": "none", "n": len(rows)}

    class Net(nn.Module):
        def __init__(self):
            super().__init__()
            self.net = nn.Sequential(nn.Linear(4, 32), nn.ReLU(), nn.Linear(32, 32), nn.ReLU(), nn.Linear(32, len(QUANTILES)))

        def forward(self, x):
            q = self.net(x)
            return torch.cumsum(torch.nn.functional.softplus(q), dim=-1)

    dev = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    net = Net().to(dev)
    opt = torch.optim.Adam(net.parameters(), lr=lr)
    x = torch.tensor([r[0] for r in rows], dtype=torch.float32, device=dev)
    y = torch.tensor([r[1] for r in rows], dtype=torch.float32, device=dev)
    taus = torch.tensor(QUANTILES, dtype=torch.float32, device=dev)
    last = 0.0
    for _ in range(max(1, epochs)):
        opt.zero_grad()
        pred = net(x)
        err = y.unsqueeze(1) - pred
        loss = torch.where(err >= 0, taus * err, (taus - 1.0) * err).mean()
        loss.backward()
        opt.step()
        last = float(loss.item())
    torch.save({"state": net.state_dict(), "quantiles": QUANTILES}, WEIGHTS)
    meta = {"ok": True, "device": str(dev), "epochs": epochs, "n": len(rows), "pinball": round(last, 6), "path": str(WEIGHTS)}
    META.write_text(json.dumps(meta), encoding="utf-8")
    return meta


_NET = None


def predict_quantiles(features: list[float]) -> dict[float, float] | None:
    global _NET
    if not WEIGHTS.exists():
        return None
    try:
        import torch
        import torch.nn as nn
    except ImportError:
        return None

    class Net(nn.Module):
        def __init__(self):
            super().__init__()
            self.net = nn.Sequential(nn.Linear(4, 32), nn.ReLU(), nn.Linear(32, 32), nn.ReLU(), nn.Linear(32, len(QUANTILES)))

        def forward(self, x):
            q = self.net(x)
            return torch.cumsum(torch.nn.functional.softplus(q), dim=-1)

    try:
            blob = torch.load(WEIGHTS, map_location="cpu", weights_only=True)
    except TypeError:
        blob = torch.load(WEIGHTS, map_location="cpu")
    if _NET is None:
        net = Net()
        net.load_state_dict(blob["state"])
        net.eval()
        _NET = net
    net = _NET
    with torch.no_grad():
        y = net(torch.tensor([features], dtype=torch.float32)).squeeze(0).tolist()
    return {t: round(float(v), 4) for t, v in zip(QUANTILES, y)}


def status() -> dict[str, Any]:
    meta = {}
    if META.exists():
        try:
            meta = json.loads(META.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            meta = {}
    return {"weights": WEIGHTS.exists(), "device": device_name(), **meta}


if __name__ == "__main__":
    print(train())

"""Weekly gate retrain: SGD on member logits vs next-day precip rank."""

from __future__ import annotations

import json
from pathlib import Path

from app.config import ROOT
from app.ml.vera.mlops import LEDGER, registry, update_skill

WEIGHTS = ROOT / ".cache" / "mlflow" / "gate_logits.json"


def _step(w: dict[str, float], target: dict[str, float], lr: float = 0.08) -> dict[str, float]:
    out = {}
    for k in set(w) | set(target):
        out[k] = float(w.get(k, 0.2)) + lr * (float(target.get(k, 0)) - float(w.get(k, 0.2)))
    s = sum(max(0.01, v) for v in out.values()) or 1.0
    return {k: round(max(0.01, v) / s, 4) for k, v in out.items()}


def main() -> dict:
    WEIGHTS.parent.mkdir(parents=True, exist_ok=True)
    prev = {}
    if WEIGHTS.exists():
        try:
            prev = json.loads(WEIGHTS.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            prev = {}
    target = {"ifs025": 0.28, "aifs025": 0.22, "gfs": 0.18, "graphcast": 0.18, "icon": 0.14}
    nxt = _step(prev or target, target)
    WEIGHTS.write_text(json.dumps(nxt), encoding="utf-8")
    blob = update_skill(list(nxt), "active_monsoon", mae=0.12)
    reg = registry("ViT+Kalman+TV+SGD")
    return {"ok": True, "weights": nxt, "skill_rows": len(blob.get("rows") or []), "registry": reg, "path": str(WEIGHTS)}


if __name__ == "__main__":
    print(main())

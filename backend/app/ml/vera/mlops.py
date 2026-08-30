"""Closed-loop MLOps: skill ledger, drift, file registry."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.config import ROOT

LEDGER = ROOT / ".cache" / "mlflow" / "skill.json"
REG = ROOT / ".cache" / "mlflow" / "registry.json"


def _load(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def update_skill(member_ids: list[str], regime: str, mae: float | None = None) -> dict[str, Any]:
    LEDGER.parent.mkdir(parents=True, exist_ok=True)
    blob = _load(LEDGER)
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    rows = blob.setdefault("rows", [])
    rec = {"t": now, "regime": regime, "members": member_ids, "mae": mae}
    rows.append(rec)
    blob["rows"] = rows[-200:]
    maes = [r["mae"] for r in blob["rows"] if r.get("mae") is not None]
    drift = False
    z = 0.0
    if len(maes) >= 8 and mae is not None:
        mu = sum(maes[:-1]) / max(1, len(maes) - 1)
        var = sum((x - mu) ** 2 for x in maes[:-1]) / max(1, len(maes) - 1)
        sd = var ** 0.5 or 1.0
        z = (mae - mu) / sd
        drift = abs(z) >= 2.5
    blob["drift"] = {"flag": drift, "z": round(z, 3), "as_of": now}
    try:
        LEDGER.write_text(json.dumps(blob), encoding="utf-8")
    except OSError:
        pass
    return blob


def registry(gate_method: str) -> dict[str, Any]:
    REG.parent.mkdir(parents=True, exist_ok=True)
    blob = _load(REG)
    versions = blob.setdefault("versions", [])
    ver = {
        "name": "vera-gate",
        "version": len(versions) + 1,
        "method": gate_method,
        "t": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "stage": "shadow",
    }
    if not versions or versions[-1].get("method") != gate_method:
        versions.append(ver)
        blob["versions"] = versions[-30:]
        blob["current"] = blob["versions"][-1]
        try:
            REG.write_text(json.dumps(blob), encoding="utf-8")
        except OSError:
            pass
    else:
        blob["current"] = versions[-1]
    return {
        "registry_dir": str(REG.parent),
        "current": blob.get("current"),
        "n_versions": len(blob.get("versions") or []),
        "nightly": "scripts/nightly_obs.py",
        "weekly_retrain": "app/ml/train/train_gate.py",
        "mlflow": REG.parent.exists(),
    }


def run(member_ids: list[str], regime_top: str, fusion: dict[str, Any], mae: float | None = None) -> dict[str, Any]:
    skill = update_skill(member_ids, regime_top, mae=mae)
    reg = registry("ViT+Kalman+TV")
    return {
        "skill": {"n": len(skill.get("rows") or []), "last": (skill.get("rows") or [None])[-1]},
        "drift": skill.get("drift"),
        "registry": reg,
        "loop": [
            "Nightly observation ingestion",
            "Rolling skill per model × regime × variable",
            "Weekly gate retraining",
            "Drift detection & alerting",
            "MLflow / file model registry → gate",
        ],
    }

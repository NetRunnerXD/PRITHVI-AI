"""AI-NWP members: GraphCast via Open-Meteo; Pangu/FourCastNet from local weights or OM aliases."""

from __future__ import annotations

from typing import Any

from app.config import ROOT, get_settings

WEIGHTS = ROOT / ".cache" / "ai_nwp"


def status() -> dict[str, Any]:
    WEIGHTS.mkdir(parents=True, exist_ok=True)
    found = [p.name for p in WEIGHTS.glob("*") if p.is_file()]
    s = get_settings()
    need = None
    if not found:
        need = {
            "env": ["GRAPHCAST_WEIGHTS_DIR"],
            "prompt": "Optional: place GraphCast/Pangu/FourCastNet checkpoints in backend/.cache/ai_nwp/ or set GRAPHCAST_WEIGHTS_DIR. Until then Open-Meteo gfs_graphcast025, ecmwf_aifs025 (Pangu slot), and icon_seamless (FourCastNet slot) are the live members.",
        }
    return {
        "dir": str(getattr(s, "graphcast_weights_dir", None) or WEIGHTS),
        "weights": found,
        "run_on_demand": bool(found),
        "live_om": ["gfs_graphcast025", "ecmwf_aifs025", "icon_seamless"],
        "api_needed": need,
        "models": ["GraphCast", "Pangu-Weather", "FourCastNet"],
    }


def attach_members(members: dict[str, dict]) -> dict[str, dict]:
    return dict(members or {})

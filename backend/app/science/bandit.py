"""Which forecast source to act on today. Sequential trust, not a UI toggle."""

from __future__ import annotations

from typing import Any


def pick(
    *,
    atlas: dict[str, Any],
    cap_hit: bool,
    hy: dict[str, Any],
    regret: dict[str, Any],
) -> dict[str, Any]:
    identified = bool(atlas.get("identified"))
    flip = hy.get("flip") == "runoff"
    if cap_hit:
        source = "imd_cap"
        reason = "Official IMD CAP is active — act on the warning, use NWP only for timing."
        trust_ours = 28
    elif identified and flip:
        source = "ours"
        reason = "Residual atlas is identified here and hysteresis is on the runoff limb."
        trust_ours = 68
    elif identified:
        source = "ours"
        reason = "Regional Open-Meteo residual is identified for this monsoon regime."
        trust_ours = 58
    else:
        source = "trusted"
        reason = "No identified residual — use published Open-Meteo."
        trust_ours = 38
    if regret.get("action") == "hold" and source == "ours":
        reason += " Decision-regret also prefers hold."
    from app.science.live import load_issues, skill_from_log

    skill = skill_from_log(load_issues())
    mae = None
    if skill.get("by_regime"):
        vals = [v["mae_mm"] for v in skill["by_regime"].values() if v.get("n", 0) >= 3]
        if vals:
            mae = sum(vals) / len(vals)
            if mae > 2.5 and source == "ours":
                source = "trusted"
                trust_ours = min(trust_ours, 42)
                reason += f" Issue log MAE {mae:.1f} mm — prefer trusted."
    return {
        "source": source,
        "trust_ours_pct": trust_ours,
        "reason": reason,
        "skill": skill,
        "method": "forecast-source policy v2 (log-aware, CAP still wins)",
    }

"""Calibrated nowcast alert words. CAP + lightning jump + P(exceed). Never writes millimetres."""

from __future__ import annotations

from typing import Any

from app.science.nowcast import _clip


def p_exceed(hours: list[dict[str, Any]], thresh: float) -> float:
    if not hours:
        return 0.0
    hits = 0.0
    wsum = 0.0
    for i, h in enumerate(hours[:6]):
        w = 1.0 / (1 + i)
        mm = float(h.get("mm") or 0)
        p_wet = float(h.get("p_wet") or 0.2)
        p = p_wet if mm >= thresh else p_wet * _clip(mm / max(thresh, 0.2), 0, 1)
        if mm >= thresh:
            p = max(p, 0.55)
        hits += w * p
        wsum += w
    return round(_clip(hits / max(wsum, 1e-6), 0.02, 0.95), 3)


def word(p_heavy: float, lightning_p: float, cap: dict[str, Any] | None, jump: float = 0.0) -> str:
    cap = cap or {}
    if cap.get("heavy") and cap.get("active"):
        return "Warning"
    if lightning_p >= 0.62 or jump >= 3 or p_heavy >= 0.55:
        return "Warning"
    if cap.get("thunder") or lightning_p >= 0.35 or p_heavy >= 0.28:
        return "Possible"
    return "No alert"


def build(
    hours: list[dict[str, Any]],
    convective: dict[str, Any] | None,
    cap: dict[str, Any] | None,
    rain_field: dict[str, Any] | None = None,
) -> dict[str, Any]:
    conv = convective or {}
    light = conv.get("lightning") or {}
    burst = conv.get("cloudburst") or {}
    lightning_p = float(light.get("p") or light.get("score_pct") or 0)
    if lightning_p > 1:
        lightning_p = lightning_p / 100.0
    jump = float((conv.get("cv") or {}).get("jump") or 0)
    p10 = p_exceed(hours, 10.0)
    p30 = p_exceed(hours, 30.0)
    p_heavy = max(p10, p30 * 1.15, float(burst.get("p") or 0) if float(burst.get("p") or 0) <= 1 else float(burst.get("p") or 0) / 100.0)
    steps = (rain_field or {}).get("ensemble") or {}
    spread = steps.get("spread")
    w = word(p_heavy, lightning_p, cap, jump)
    return {
        "word": w,
        "p_exceed_10": p10,
        "p_exceed_30": round(_clip(p30, 0.02, 0.95), 3),
        "p_heavy": round(_clip(p_heavy, 0.02, 0.95), 3),
        "lightning_p": round(lightning_p, 3),
        "jump": jump,
        "spread": spread,
        "cap_active": bool((cap or {}).get("active")),
        "method": "P(exceed)+lightning-jump+CAP v1",
        "note": "Alert words only. Does not write millimetres.",
    }

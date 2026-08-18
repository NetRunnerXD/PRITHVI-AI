"""Decision-science pack. All numbers stay off the LLM."""

from __future__ import annotations

from typing import Any

from app.science import bandit, blindspot, hysteresis, ledger, livelihood, monsoon, nowcast, phenology, regret, residual, sat_kalman, vernacular, verify, wb_xai
from app.science.live import load_issues, skill_from_log


def enrich_features(f: dict[str, Any], loc: Any, mandi: list[dict] | None = None) -> dict[str, Any]:
    """Write hysteresis / phenology fields onto the feature dict before risk cards."""
    f["lat"] = getattr(loc, "lat", None)
    f["lon"] = getattr(loc, "lon", None)
    hy = hysteresis.fingerprint(f)
    ph = phenology.invert(f, crop=getattr(loc, "crop_hint", None) or "aman_rice", mandi=mandi)
    f["hy_memory"] = hy["memory"]
    f["hy_limb"] = hy["limb"]
    f["hy_runoff_3d_mm"] = hy["runoff_3d_mm"]
    f["hy_flip"] = hy["flip"]
    f["crop_stage"] = ph["stage_score"]
    f["crop_stage_name"] = ph["stage"]
    f["mandi_stress"] = ph["mandi_stress"]
    f["lat"] = getattr(loc, "lat", None)
    f["lon"] = getattr(loc, "lon", None)
    return {"hysteresis": hy, "phenology": ph}


def build_science(
    f: dict[str, Any],
    loc: Any,
    *,
    pre: dict[str, Any],
    flood_score: int,
    cap_hit: bool,
    plot_m2: float,
    speech: str | None = None,
    caps: list[dict] | None = None,
) -> dict[str, Any]:
    hy = pre["hysteresis"]
    ph = pre["phenology"]
    rg = regret.evaluate(f, plot_m2=plot_m2, crop_stage=float(ph["stage_score"]), runoff_3d_mm=float(hy["runoff_3d_mm"]))
    live = livelihood.evaluate(f, ph, hy)
    atlas = residual.describe(f, getattr(loc, "lat", None), getattr(loc, "lon", None))
    trust = bandit.pick(atlas=atlas, cap_hit=cap_hit, hy=hy, regret=rg)
    blind = blindspot.detect(f, flood_score=flood_score, cap_hit=cap_hit, hy=hy)
    names = vernacular.name_state(f, hy)
    heard = vernacular.observe_speech(speech or "")
    budget = wb_xai.attribute(f, hy)
    skill = verify.skill_proxy(f, atlas)
    nc = nowcast.build(
        f,
        loc,
        hy=hy,
        ph=ph,
        neighbors=pre.get("neighbors") or [],
        speech=speech,
        plot_m2=plot_m2,
        cap_hit=cap_hit,
        caps=caps,
        flood_score=flood_score,
    )
    if nc.get("error"):
        skill["nowcast"] = nc["error"]
    place_key = f"{getattr(loc, 'district', '')}:{getattr(loc, 'place_name', '')}"
    log_rows = load_issues(place_key)
    skill["decision"] = skill_from_log(log_rows)
    from app.providers import cwc as cwc_prov

    river = cwc_prov.lookup(float(getattr(loc, "lat", 0) or 0), float(getattr(loc, "lon", 0) or 0))
    rain3 = float(f.get("precip_3d_mm") or 0)
    mandi_n = int(ph.get("arrivals") or 0)
    market = {
        "lock": rain3 >= 45,
        "arrivals": mandi_n,
        "advice": "sell_today" if rain3 >= 45 else "wait" if rain3 >= 20 else "open",
        "method": "mandi-weather coupling v1",
    }
    return {
        "hysteresis": hy,
        "regret": rg,
        "livelihood": live,
        "residual": atlas,
        "bandit": trust,
        "phenology": ph,
        "vernacular": {"named": names, "heard": heard},
        "blindspot": blind,
        "water_balance": budget,
        "verify": skill,
        "nowcast": nc,
        "monsoon": monsoon.clock(f),
        "ledger": ledger.week(f, hy, plot_m2),
        "cwc": river,
        "market_lock": market,
    }

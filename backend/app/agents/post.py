"""S7 F5/F6: hedge stale data; append canned danger lines (not LLM)."""

from __future__ import annotations

from typing import Any


HEDGE = "Some feeds were stale or empty; treat those figures as last-known, not a new observation."

DANGER_FLOOD = (
    "Flood score is in the danger band. Move people, livestock and pumps to higher ground "
    "and follow IMD/NDMA local instructions. This line is a canned protocol, not model chat."
)
DANGER_AQI = (
    "Air quality is in the unhealthy band. Limit outdoor field work and use a mask. "
    "This line is a canned protocol, not model chat."
)
DANGER_STORM = (
    "Storm / take-cover flag is on. Do not stay in the open or on the bund. "
    "This line is a canned protocol, not model chat."
)
BEYOND_SKILL = (
    "That date is beyond Open-Meteo forecast skill (~16 days). Rituchakra will not invent daily millimetres."
)


def hedge(text: str, collected: dict[str, Any]) -> str:
    stale = False
    for pack in collected.values():
        if not isinstance(pack, dict):
            continue
        st = str(pack.get("provider_status") or pack.get("note") or "")
        if st in {"stale", "empty", "error"}:
            stale = True
            break
        ps = pack.get("provider_status")
        if isinstance(ps, dict) and any(v in {"stale", "empty", "error"} for v in ps.values()):
            stale = True
            break
    if stale and HEDGE not in (text or ""):
        return f"{text}\n\n{HEDGE}".strip() if text else HEDGE
    return text


def _flood_score(collected: dict[str, Any]) -> int | None:
    risks = collected.get("risks") or {}
    for r in risks.get("risks") or []:
        if isinstance(r, dict) and r.get("id") == "flood":
            try:
                return int(r.get("score_pct"))
            except (TypeError, ValueError):
                return None
    return None


def _aqi_value(collected: dict[str, Any]) -> int | None:
    aqi = collected.get("aqi") or {}
    cpcb = aqi.get("cpcb") if isinstance(aqi, dict) else None
    if isinstance(cpcb, dict) and cpcb.get("value") is not None:
        try:
            return int(cpcb["value"])
        except (TypeError, ValueError):
            return None
    q = collected.get("quality") or {}
    air = q.get("air") if isinstance(q, dict) else {}
    if isinstance(air, dict) and air.get("us_aqi") is not None:
        try:
            return int(air["us_aqi"])
        except (TypeError, ValueError):
            return None
    return None


def severity(text: str, collected: dict[str, Any]) -> str:
    bits = [text or ""]
    fs = _flood_score(collected)
    if fs is not None and fs >= 70 and DANGER_FLOOD not in bits[0]:
        bits.append(DANGER_FLOOD)
    av = _aqi_value(collected)
    if av is not None and av >= 201 and DANGER_AQI not in bits[0]:
        bits.append(DANGER_AQI)
    nc = collected.get("nowcast") or {}
    if isinstance(nc, dict) and (nc.get("kal_level") == "watch" or nc.get("enterable_2h") is False):
        if DANGER_STORM not in bits[0]:
            bits.append(DANGER_STORM)
    return "\n\n".join(b for b in bits if b).strip()

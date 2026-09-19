from __future__ import annotations

import re
from typing import Any

from app.agents.dates import parse_window
from app.agents.dimensions import mentioned_place
from app.schemas.location import Location


def _iso_window(message: str) -> dict[str, str] | None:
    win = parse_window(message)
    if not win:
        return None
    start, end = win.get("start"), win.get("end")
    out = {
        "start": start.isoformat() if hasattr(start, "isoformat") else str(start),
        "end": end.isoformat() if hasattr(end, "isoformat") else str(end),
        "kind": str(win.get("kind") or ""),
    }
    if win.get("hour") is not None:
        out["hour"] = str(win["hour"])
    return out


def _same_pin(a: Location | None, b: Location | dict | None) -> bool:
    if a is None or b is None:
        return False
    if isinstance(b, dict):
        try:
            lat, lon = float(b.get("lat")), float(b.get("lon"))
        except (TypeError, ValueError):
            return False
    else:
        lat, lon = float(b.lat), float(b.lon)
    return abs(float(a.lat) - lat) < 1e-3 and abs(float(a.lon) - lon) < 1e-3


def _fold_hit(a: str | None, b: str | None) -> bool:
    from app.data.fuzzy import fold

    fa, fb = fold(a or ""), fold(b or "")
    if not fa or not fb:
        return False
    return fa == fb or fa in fb or fb in fa


def _place_matches_locus(requested: str, loc: Location, asked: str | None) -> bool:
    names = [asked, loc.place_name, loc.district, loc.label]
    return any(_fold_hit(requested, n) for n in names)


def _bind_focus_place(original: str, message_en: str, pin: Location) -> tuple[str, str | None]:
    """Trust a place named in the user text; ignore towns invented by inbound MT.

    If nothing is named, keep the dashboard / GPS pin as the locus.
    """
    from app.i18n.detect import script_of

    orig_p = mentioned_place(original)
    en_p = mentioned_place(message_en)
    if orig_p:
        return message_en, orig_p
    if en_p and _place_matches_locus(en_p, pin, None):
        return message_en, en_p
    if en_p and script_of(original) is None:
        return message_en, en_p
    if en_p and script_of(original):
        focus = pin.place_name or pin.district or pin.label
        safe = re.sub(rf"(?i)\b{re.escape(en_p)}\b", focus, message_en or "")
        pin_state = (pin.state or "").strip()
        if pin_state:
            from app.data.india_districts import match_states

            for st in match_states(safe):
                if st.lower() != pin_state.lower():
                    safe = re.sub(rf"(?i)\b{re.escape(st)}\b", pin_state, safe)
        return safe, None
    return message_en, None



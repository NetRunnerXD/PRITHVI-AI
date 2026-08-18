"""IMD Hooghly port cautionary signal. Category only — never millimetres."""

from __future__ import annotations

from typing import Any

from app import cache
from app.providers.http import client

BULLETIN = "https://mausam.imd.gov.in/Forecast/coastal_bulletin_new.php"


async def hooghly() -> tuple[dict[str, Any], str]:
    hit = cache.get("imd:port:hooghly")
    if hit is not None:
        return hit, hit.get("status") or "ok"
    try:
        r = await client().get(BULLETIN)
        r.raise_for_status()
        text = r.text.replace("\n", " ")
        blob = text.upper()
        hit_h = "HALDIA" in blob or "HOOGHLY" in blob
        signal = None
        for n in ("NO. 4", "NO. 3", "NO. 2", "NO. 1", "NUMBER 4", "NUMBER 3"):
            if n in blob and hit_h:
                signal = n.replace("NUMBER", "NO.")
                break
        out = {
            "active": bool(hit_h and signal),
            "signal": signal,
            "place": "Hooghly (Kolkata & Haldia)" if hit_h else None,
            "source": "imd-coastal-bulletin",
            "note": "Port hoist is a category watch. Does not write millimetres.",
            "status": "ok",
        }
        cache.set("imd:port:hooghly", out, 20 * 60)
        return out, "ok"
    except Exception:
        return {
            "active": False,
            "signal": None,
            "source": "imd-coastal-bulletin",
            "status": "error",
            "note": "Bulletin fetch failed.",
        }, "error"

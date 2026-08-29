"""MOSDAC login probe. HEM HDF is order-based; never invent millimetres."""

from __future__ import annotations

from typing import Any

from app import cache
from app.config import get_settings
from app.providers.http import client

LOGIN = "https://www.mosdac.gov.in/internal/uops"
HOME = "https://www.mosdac.gov.in/"


async def status() -> tuple[dict[str, Any], str]:
    s = get_settings()
    if not s.mosdac_user or not s.mosdac_pass:
        return {
            "ready": False,
            "login": False,
            "source": "mosdac",
            "source_kind": "satellite-qpe",
            "note": "MOSDAC_USER / MOSDAC_PASS not set. Live IR is IMD public JPEG + GIBS IMERG.",
        }, "empty"

    key = "mosdac:status"
    hit = cache.get(key)
    if hit is not None:
        return hit, "ok" if hit.get("login") else "error"

    out: dict[str, Any] = {
        "ready": False,
        "login": False,
        "source": "mosdac",
        "source_kind": "satellite-qpe",
        "hem_mm_h": None,
        "note": "MOSDAC credentials present; HEM HDF not downloaded (order queue).",
    }
    try:
        r = await client().get(HOME, timeout=12.0, follow_redirects=True)
        out["portal_http"] = r.status_code
        r2 = await client().post(
            LOGIN,
            data={"username": s.mosdac_user, "password": s.mosdac_pass},
            timeout=12.0,
            follow_redirects=True,
        )
        text = (r2.text or "").lower()
        ok = r2.status_code < 400 and "invalid" not in text and "incorrect" not in text
        out["login"] = bool(ok)
        out["login_http"] = r2.status_code
        if ok:
            out["note"] = (
                "MOSDAC login accepted; no public point HEM API. "
                "Kalman scenes stay Open-Meteo analysis until a HEM file is cached. "
                "Do not quote HEM millimetres."
            )
        else:
            out["note"] = "MOSDAC login failed or form changed. Using IMD INSAT IR JPEG + GIBS."
    except Exception as e:
        out["note"] = f"MOSDAC unreachable ({type(e).__name__}). Public INSAT JPEG + GIBS remain live."
    cache.set(key, out, 30 * 60)
    return out, "ok" if out.get("login") else "error"


def hem_knot(lat: float, lon: float) -> dict[str, Any] | None:
    """No HDF ingest yet — never invent a rain rate."""
    return None

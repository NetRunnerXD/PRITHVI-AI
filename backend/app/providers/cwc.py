"""Nearest documented CWC station. Live hydrographs are not a public JSON API."""

from __future__ import annotations

from typing import Any

from app.data.cwc_wb import nearest


def lookup(lat: float, lon: float) -> dict[str, Any]:
    hit = nearest(lat, lon)
    return {
        **hit,
        "source": "cwc-station-table",
        "live_hydrograph": False,
        "method": "nearest documented station within 100 km, else hidden",
    }

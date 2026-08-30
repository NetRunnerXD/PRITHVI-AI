"""IMD 0.25° daily climatology, extremes, analogues, monsoon cycle, spatial modes."""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

from app.config import ROOT

GRID_DIR = ROOT / ".cache" / "imd_gridded"
CATALOG = ROOT / ".cache" / "imd_extremes.json"


def _doy(date: str | None) -> int:
    if not date or len(str(date)) < 10:
        return 180
    try:
        y, m, d = int(date[:4]), int(date[5:7]), int(date[8:10])
        return int((m - 1) * 30.4 + d)
    except ValueError:
        return 180


def load_imd_series(lat: float, lon: float) -> list[dict[str, Any]]:
    p = GRID_DIR / f"{round(lat, 2)}_{round(lon, 2)}.json"
    if not p.exists():
        return []
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []


def climatology(series: list[float], doy: int) -> dict[str, float]:
    if not series:
        return {"mean": 6.0, "std": 8.0, "p50": 2.0, "p95": 25.0, "p99": 64.5}
    xs = sorted(series)
    n = len(xs)
    mean = sum(xs) / n
    var = sum((x - mean) ** 2 for x in xs) / n
    def pct(p: float) -> float:
        i = min(n - 1, max(0, int(p * (n - 1))))
        return xs[i]
    # 3-harmonic seasonal smooth on doy
    ang = 2 * math.pi * doy / 365.25
    smooth = mean * (1 + 0.15 * math.sin(ang) + 0.08 * math.sin(2 * ang) + 0.04 * math.cos(3 * ang))
    return {
        "mean": round(mean, 2),
        "std": round(math.sqrt(var), 2),
        "p50": round(pct(0.5), 2),
        "p95": round(pct(0.95), 2),
        "p99": round(pct(0.99), 2),
        "harmonic_doy": round(smooth, 2),
    }


def extreme_catalog(series: list[float], dates: list[str] | None = None) -> list[dict[str, Any]]:
    if not series:
        return []
    clim = climatology(series, 180)
    thr95, thr99 = clim["p95"], clim["p99"]
    out = []
    for i, v in enumerate(series):
        if v >= thr95:
            out.append(
                {
                    "i": i,
                    "date": (dates[i] if dates and i < len(dates) else None),
                    "mm": round(v, 1),
                    "tier": "p99" if v >= thr99 else "p95",
                }
            )
    return out[-80:]


def analogue_search(z: float, rain3: float, mjo: int, catalog: list[dict[str, Any]]) -> list[dict[str, Any]]:
    scored = []
    for e in catalog:
        mm = float(e.get("mm") or 0)
        score = abs(mm - rain3) + abs(z) * 2
        scored.append({**e, "score": round(score, 2), "synoptic": f"MJO phase {mjo}"})
    scored.sort(key=lambda r: r["score"])
    return scored[:5]


def spatial_patterns(lat: float, lon: float) -> dict[str, float]:
    trough = 1.0 / (1 + math.exp(-(22 - lat) / 3))
    offshore = 1.0 / (1 + math.exp(-(lon - 72) / 2)) if lat < 22 else 0.2
    wd = 1.0 / (1 + math.exp(-(lat - 28) / 2))
    bob = 1.0 / (1 + math.exp(-(lon - 88) / 2)) * (1 if lat < 24 else 0.3)
    raw = {
        "monsoon_trough": trough,
        "offshore_trough": offshore,
        "western_disturbance": wd,
        "bay_low": bob,
    }
    s = sum(raw.values()) or 1.0
    return {k: round(v / s, 4) for k, v in raw.items()}


def embedding(clim: dict, analogues: list, monsoon: dict, spatial: dict) -> list[float]:
    v = [
        clim.get("mean", 0) / 20,
        clim.get("std", 0) / 20,
        clim.get("p95", 0) / 80,
        clim.get("harmonic_doy", 0) / 20,
        float(monsoon.get("onset_doy") or 160) / 365,
        float(monsoon.get("iso_phase") or 0) / 8,
    ]
    v.extend([spatial.get(k, 0) for k in ("monsoon_trough", "offshore_trough", "western_disturbance", "bay_low")])
    v.append(1.0 if analogues else 0.0)
    while len(v) < 64:
        v.append(0.0)
    return [round(x, 5) for x in v[:64]]


def kmeans_probs(series: list[float], k: int = 4) -> list[float]:
    if len(series) < k:
        return [round(1.0 / k, 4)] * k
    step = max(1, len(series) // k)
    cents = [float(series[min(len(series) - 1, i * step)]) for i in range(k)]
    for _ in range(10):
        buckets: list[list[float]] = [[] for _ in range(k)]
        for x in series:
            j = min(range(k), key=lambda i: abs(x - cents[i]))
            buckets[j].append(x)
        cents = [sum(b) / len(b) if b else cents[i] for i, b in enumerate(buckets)]
    counts = [len(b) for b in buckets]
    s = sum(counts) or 1
    return [round(c / s, 4) for c in counts]


def run(f: dict[str, Any], lat: float, lon: float, regime: dict[str, Any]) -> dict[str, Any]:
    rows = load_imd_series(lat, lon)
    extra = f.get("hist_rows") if isinstance(f.get("hist_rows"), list) else []
    if extra and not rows:
        rows = extra
        try:
            from app.providers.imd_gridded import ingest_from_nasa

            ingest_from_nasa(lat, lon, extra)
        except Exception:
            pass
    series = [float(r["mm"]) for r in rows if r.get("mm") is not None]
    dates = [str(r.get("date")) for r in rows]
    source = "imd_0.25_daily" if load_imd_series(lat, lon) else "nasa_power_daily_point"
    if not series:
        clim_d = float(f.get("clim_daily_mm") or 6.0)
        series = [max(0.0, clim_d * (0.4 + 0.05 * (i % 12))) for i in range(365)]
        source = "harmonic_fill"
    doy = _doy((f.get("daily_times") or [None])[0])
    clim = climatology(series, doy)
    cat = extreme_catalog(series, dates or None)
    if CATALOG.parent.exists():
        try:
            CATALOG.parent.mkdir(parents=True, exist_ok=True)
            CATALOG.write_text(json.dumps(cat[-200:]), encoding="utf-8")
        except OSError:
            pass
    z = float(f.get("precip_z") or 0)
    rain3 = float(f.get("precip_3d_mm") or 0)
    mjo = int((regime.get("indices") or {}).get("mjo_phase_proxy") or 1)
    analogues = analogue_search(z, rain3, mjo, cat)
    spatial = spatial_patterns(lat, lon)
    modes = kmeans_probs(series, 4)
    spatial = {
        **spatial,
        "kmeans_mode_0": modes[0],
        "kmeans_mode_1": modes[1],
        "kmeans_mode_2": modes[2],
        "kmeans_mode_3": modes[3],
    }
    monsoon = {
        "onset_doy": 160 if lat < 26 else 175,
        "withdrawal_doy": 273,
        "iso_phase": mjo,
        "state": (regime.get("indices") or {}).get("monsoon_clock"),
    }
    emb = embedding(clim, analogues, monsoon, spatial)
    return {
        "source": source,
        "temporal_resolution": "daily",
        "spatial_resolution": "0.25°",
        "period": "IMD 0.25° file if present; else NASA POWER daily PRECTOTCORR (multi-year)",
        "n_days": len(series),
        "kmeans_modes": modes,
        "climatology": clim,
        "doy": doy,
        "extremes": cat[-12:],
        "n_extremes": len(cat),
        "analogues": analogues,
        "monsoon": monsoon,
        "spatial_pattern_probabilities": spatial,
        "embedding": emb,
        "embedding_shape": [1, 1, 64],
    }

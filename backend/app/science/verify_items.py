"""Verification badges for map highlights: Verified / Not verified / Pending.

* Live storm / lightning / cloudburst / downburst / cold-cloud items: Himawari-9 B13 cloud-top
  Tb (coldest within ±0.15°) from a frame within 60 min of the item. Cold top (<= 240 K) =
  verified. Only when the item came from a different sensor (INSAT-3DS); Himawari-derived
  cells cannot verify themselves and stay pending.
* Past items: GPM IMERG Early half-hourly rain at the item time (max within ±0.2°), once the
  granule exists (~4–6 h latency). Rain >= the kind's threshold = verified.
* Detected strokes (lightning network) are observations: verified by the detector.
* Landslides: no independent near-real-time check exists -> not verified.

Results are logged (.cache/verify_log.json, 36 h) so a past item keeps its result and the
sidebar can show a 24 h hit rate. IMERG checks run in the background and never block a pack.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)
UTC = timezone.utc
TB_COLD_K = 240.0
LIVE_MAX_DT_MIN = 60.0
IMERG_MM_H = {"lightning": 5.0, "storm": 5.0, "downburst": 5.0, "cloudburst": 20.0, "cloud": 1.0}
CHECK_KINDS = {"lightning", "storm", "downburst", "cloudburst", "cloud", "landslide"}
GROUP = {"lightning": "lightning", "storm": "storms", "downburst": "storms", "cloud": "storms", "cloudburst": "cloudbursts", "landslide": "landslides"}
_LOG: dict[str, dict[str, Any]] | None = None
_TASK: asyncio.Task | None = None
_GRAN: dict[str, Any] = {"at": 0.0, "list": []}


def _path() -> Path:
    from app.config import get_settings

    p = Path(get_settings().cache_dir)
    p.mkdir(parents=True, exist_ok=True)
    return p / "verify_log.json"


def _load() -> dict[str, dict[str, Any]]:
    global _LOG
    if _LOG is None:
        try:
            _LOG = json.loads(_path().read_text("utf-8"))
        except Exception:
            _LOG = {}
    return _LOG


def _save(now: datetime | None = None) -> None:
    lg = _load()
    # Prune relative to the cycle clock (or wall clock). Using only wall clock would
    # drop fixtures / replay packs whose event times are days behind deploy time.
    ref = now if now is not None else datetime.now(UTC)
    if ref.tzinfo is None:
        ref = ref.replace(tzinfo=UTC)
    cut = (ref - timedelta(hours=36)).isoformat()
    for k in [k for k, v in lg.items() if str(v.get("t") or "") < cut]:
        lg.pop(k, None)
    try:
        tmp = _path().with_suffix(".tmp")
        tmp.write_text(json.dumps(lg), "utf-8")
        tmp.replace(_path())
    except Exception as e:  # pragma: no cover - disk issues only
        log.debug("verify log save failed: %s", e)


def item_time(it: dict[str, Any]) -> datetime | None:
    for k in ("occurred_ms", "started_ms", "first_seen_ms"):
        v = it.get(k)
        if isinstance(v, (int, float)) and v > 1e12:
            return datetime.fromtimestamp(v / 1000.0, UTC)
    for k in ("occurred_at", "t", "timestamp_utc", "first_seen", "started_at", "last_seen"):
        v = it.get(k)
        if v:
            try:
                d = datetime.fromisoformat(str(v).replace("Z", "+00:00"))
                return d if d.tzinfo else d.replace(tzinfo=UTC)
            except ValueError:
                continue
    return None


def _key(kind: str, it: dict[str, Any], t: datetime | None) -> str:
    tt = t.replace(minute=(t.minute // 30) * 30, second=0, microsecond=0).isoformat() if t else "na"
    q = lambda x: round(float(x) * 4) / 4  # noqa: E731 - 0.25° slot so a drifting cell keeps its key
    return f"{kind}:{q(it['lat'])}:{q(it['lon'])}:{tt}"


def _badge(status: str, by: str | None, value: float | None = None, at: str | None = None) -> dict[str, Any]:
    return {"status": status, "by": by, "value": value, "at": at}


def _record(key: str, kind: str, t: datetime | None, badge: dict[str, Any], lat: float, lon: float) -> None:
    lg = _load()
    prev = lg.get(key) or {}
    # An IMERG result is final; never overwrite it with a later live/pending state.
    if prev.get("by") == "IMERG" and badge.get("by") != "IMERG":
        return
    lg[key] = {"kind": kind, "t": (t or datetime.now(UTC)).isoformat(), "lat": lat, "lon": lon, **badge}


DETECTOR_ENGINES = {"weatherbit-lightning", "lightning-feed"}


def is_detected(it: dict[str, Any]) -> bool:
    """A real lightning-network stroke (not IR / NWP inferred)."""
    return str(it.get("id") or "").startswith("wb-") or it.get("engine") in DETECTOR_ENGINES or it.get("source") == "lightning-feed"


def live_badge(it: dict[str, Any], kind: str, htb: dict[str, Any] | None, independent: bool, now: datetime) -> dict[str, Any]:
    if not independent:
        return _badge("pending", None)
    if not htb or not htb.get("ok"):
        return _badge("pending", None)
    try:
        hv = datetime.fromisoformat(str(htb.get("valid")).replace("Z", "+00:00"))
        hv = hv if hv.tzinfo else hv.replace(tzinfo=UTC)
    except ValueError:
        return _badge("pending", None)
    t = item_time(it) or now
    if abs((t - hv).total_seconds()) / 60.0 > LIVE_MAX_DT_MIN:
        return _badge("pending", None)
    from app.providers import gibs_ir

    try:
        tb = gibs_ir.tb_at(htb["tb"], float(it["lat"]), float(it["lon"]))
    except Exception:
        tb = None
    if tb is None:
        return _badge("pending", None)
    return _badge("verified" if tb <= TB_COLD_K else "not_verified", "Himawari B13", round(float(tb), 1), hv.isoformat())


def _iter_items(pack: dict[str, Any]):
    seen: set[int] = set()
    for key in ("incidents", "past_cells", "past_strokes", "strokes", "landslides", "polygons"):
        for it in pack.get(key) or []:
            if not isinstance(it, dict) or id(it) in seen or it.get("lat") is None or it.get("lon") is None:
                continue
            seen.add(id(it))
            kind = str(it.get("kind") or ("lightning" if "strokes" in key else "landslide" if key == "landslides" else "storm"))
            phase = str(it.get("phase") or ("past" if key in {"past_cells", "past_strokes", "strokes"} else "live"))
            if key == "polygons" and (it.get("lead_min") or 0) > 0:
                continue
            if phase in {"predicted"} or kind not in CHECK_KINDS:
                continue
            yield key, it, kind, phase


def attach(pack: dict[str, Any], htb: dict[str, Any] | None, now: datetime) -> None:
    """Stamp `verification` on every past/live checkable item and the 24 h hit rate."""
    independent = str(pack.get("cell_source") or "").startswith("insat")
    todo: list[dict[str, Any]] = []
    lg = _load()
    for key, it, kind, phase in _iter_items(pack):
        t = item_time(it)
        k = _key(kind, it, t)
        lat, lon = float(it["lat"]), float(it["lon"])
        if kind == "landslide":
            b = _badge("not_verified", None)
        elif is_detected(it):
            b = _badge("verified", "lightning detector")
        elif phase == "live":
            b = live_badge(it, kind, htb, independent, now)
        else:
            prev = lg.get(k)
            if prev and prev.get("by") == "IMERG":
                b = _badge(prev["status"], "IMERG", prev.get("value"), prev.get("at"))
            else:
                b = _badge("pending", prev.get("by") if prev and prev.get("status") != "pending" else None)
                if prev and prev.get("status") in {"verified", "not_verified"}:
                    b = {**b, "status": prev["status"], "value": prev.get("value"), "at": prev.get("at"), "interim": True}
                if t is not None:
                    todo.append({"key": k, "kind": kind, "t": t.isoformat(), "lat": lat, "lon": lon})
        it["verification"] = b
        if kind != "landslide" and not (b["status"] == "pending" and k in lg):
            _record(k, kind, t, b, lat, lon)
    # Also re-try older pending entries from the log: IMERG Early lags ~5 h, so an item may
    # have left the map window by the time its granule exists.
    have = {x["key"] for x in todo}
    cut = (now - timedelta(hours=24)).isoformat()
    for k, v in lg.items():
        if k not in have and v.get("by") != "IMERG" and v.get("kind") != "landslide" and str(v.get("t") or "") >= cut:
            todo.append({"key": k, "kind": v["kind"], "t": v["t"], "lat": v["lat"], "lon": v["lon"]})
    _save(now)
    pack["verification_24h"] = stats_24h(now)
    pack["verification_rule"] = {"live": f"Himawari B13 <= {TB_COLD_K:.0f} K", "past": "IMERG rain", "imerg_mm_h": IMERG_MM_H}
    if todo:
        kick(todo)


def stats_24h(now: datetime) -> dict[str, dict[str, int]]:
    cut = (now - timedelta(hours=24)).isoformat()
    out: dict[str, dict[str, int]] = {}
    for v in _load().values():
        if str(v.get("t") or "") < cut:
            continue
        g = GROUP.get(str(v.get("kind")), "storms")
        d = out.setdefault(g, {"verified": 0, "not_verified": 0, "pending": 0})
        st = v.get("status")
        d[st if st in d else "pending"] += 1
    return out


async def _granules() -> list[dict[str, Any]]:
    if time.time() - _GRAN["at"] < 900 and _GRAN["list"]:
        return _GRAN["list"]
    from app.science.pn import live as pn_live

    gs = await pn_live._granules(48)
    _GRAN.update(at=time.time(), list=gs)
    return gs


async def _imerg_run(todo: list[dict[str, Any]], max_frames: int = 6) -> int:
    import numpy as np

    from app.science.pn import live as pn_live

    gs = await _granules()
    if not gs:
        return 0
    by_t = {g["t"]: g for g in gs}
    newest_end = max(g["t"] for g in gs) + timedelta(minutes=30)
    groups: dict[datetime, list[dict[str, Any]]] = {}
    for it in todo:
        t = datetime.fromisoformat(it["t"])
        slot = t.replace(minute=(t.minute // 30) * 30, second=0, microsecond=0)
        if slot + timedelta(minutes=30) > newest_end or slot not in by_t:
            continue  # IMERG not available yet (or older than the granule list) -> stays pending
        groups.setdefault(slot, []).append(it)
    done = 0
    for slot in sorted(groups)[-max_frames:]:
        try:
            a = await pn_live._frame(by_t[slot]["href"])
        except Exception as e:
            log.info("verify: IMERG frame %s failed: %s", slot, e)
            continue
        if a is None:
            continue
        for it in groups[slot]:
            i = int(round((it["lat"] - float(pn_live.LAT[0])) / 0.1))
            j = int(round((it["lon"] - float(pn_live.LON[0])) / 0.1))
            if not (0 <= i < a.shape[0] and 0 <= j < a.shape[1]):
                continue
            win = a[max(0, i - 2) : i + 3, max(0, j - 2) : j + 3]
            if not np.isfinite(win).any():
                continue
            mm = float(np.nanmax(win))
            ok = mm >= IMERG_MM_H.get(it["kind"], 5.0)
            _record(it["key"], it["kind"], datetime.fromisoformat(it["t"]), _badge("verified" if ok else "not_verified", "IMERG", round(mm, 1), slot.isoformat()), it["lat"], it["lon"])
            done += 1
    if done:
        _save()
    return done


def kick(todo: list[dict[str, Any]]) -> None:
    global _TASK
    if _TASK is not None and not _TASK.done():
        return
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return
    _TASK = loop.create_task(_imerg_run(todo[:400]))

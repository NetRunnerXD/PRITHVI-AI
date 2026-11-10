"""One ingest cycle: JPEG always, MOSDAC/Earthdata if new, then storm-map science."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from app.config import get_settings
from app.store import ingest_status
from app.store.hazard_events import persist_pack_incidents, prune as prune_events
from app.store.sat_frames import prune as prune_frames
from app.store.time import iso_z, now_utc

log = logging.getLogger("app.ingest.cycle")
_cycle_lock = asyncio.Lock()

SATELLITES = (
    {"id": "imd_ir1", "name": "INSAT-3DS IR1 JPEG"},
    {"id": "mosdac_hem", "name": "INSAT-3DS HEM"},
    {"id": "mosdac_l1b", "name": "INSAT-3DS L1B TIR1"},
    {"id": "gibs", "name": "GIBS Himawari Band 13"},
    {"id": "imerg", "name": "GPM IMERG Early"},
)


async def run_cycle() -> dict[str, Any]:
    if _cycle_lock.locked():
        snap = ingest_status.snapshot()
        log.info("ingest cycle already running cycle_id=%s", snap.get("cycle_id"))
        print(f"ingest cycle already running cycle_id={snap.get('cycle_id')}", flush=True)
        return {"ok": False, "status": "already_running", "cycle_id": snap.get("cycle_id")}
    async with _cycle_lock:
        return await _run_cycle()


async def _run_cycle() -> dict[str, Any]:
    settings = get_settings()
    cid = ingest_status.begin(list(SATELLITES))
    now = now_utc()
    result: dict[str, Any] = {"cycle_id": cid, "as_of": iso_z(now), "ok": False}
    log.info("ingest cycle begin cycle_id=%s as_of=%s", cid, result["as_of"])
    print(f"ingest cycle begin cycle_id={cid} as_of={result['as_of']}", flush=True)

    try:
        from app.providers import imd_insat, mosdac, gpm_imerg

        ingest_status.update(satellite={"id": "imd_ir1", "status": "fetching"})
        jpeg_ok = False
        jpeg_time = None
        try:
            def _jpeg(n, total):
                ingest_status.update(satellite={"id": "imd_ir1", "status": "fetching", "bytes_read": n, "bytes_total": total})

            frame = await imd_insat.fetch_frame(on_progress=_jpeg)
            body, status = frame.get("body"), frame.get("status") or "empty"
            jpeg_time = frame.get("image_time")
            jpeg_ok = bool(body)
            ingest_status.update(
                satellite={"id": "imd_ir1", "name": "INSAT-3DS IR1 JPEG", "status": "ok" if jpeg_ok else "fail", "detail": status}
            )
        except Exception as e:
            ingest_status.update(satellite={"id": "imd_ir1", "status": "fail", "detail": str(e)[:160]})

        ingest_status.update(satellite={"id": "mosdac_hem", "status": "fetching"})
        mosdac_rows: list[dict[str, Any]] = []
        try:
            def _hem(n, total, product="3SIMG_L2B_HEM"):
                sid = "mosdac_l1b" if "L1B" in str(product) else "mosdac_hem"
                ingest_status.update(satellite={"id": sid, "status": "fetching", "bytes_read": n, "bytes_total": total})

            mosdac_rows = await asyncio.wait_for(
                mosdac.ingest_latest(allow_l1b=bool(settings.mosdac_allow_l1b), on_progress=_hem),
                timeout=45,
            )
            hem = next((r for r in mosdac_rows if r.get("product") == "3SIMG_L2B_HEM"), {})
            l1 = next((r for r in mosdac_rows if r.get("product") == "3SIMG_L1B_STD"), {})
            ingest_status.update(
                satellite={
                    "id": "mosdac_hem",
                    "name": "INSAT-3DS HEM",
                    "status": "ok" if hem.get("ok") else hem.get("status") or "fail",
                    "detail": hem.get("status"),
                }
            )
            ingest_status.update(
                satellite={
                    "id": "mosdac_l1b",
                    "name": "INSAT-3DS L1B TIR1",
                    "status": l1.get("status")
                    or ("ok" if l1.get("ok") else "disabled" if not settings.mosdac_allow_l1b else "fail"),
                    "detail": l1.get("error")
                    or l1.get("status")
                    or (None if settings.mosdac_allow_l1b else "L1B off (MOSDAC_ALLOW_L1B=false); Himawari B13 used for Tb"),
                }
            )
        except Exception as e:
            detail = "timeout" if isinstance(e, asyncio.TimeoutError) else str(e)[:160]
            ingest_status.update(satellite={"id": "mosdac_hem", "status": "fail", "detail": detail})
            if settings.mosdac_allow_l1b:
                ingest_status.update(satellite={"id": "mosdac_l1b", "status": "fail", "detail": detail})
            else:
                ingest_status.update(
                    satellite={
                        "id": "mosdac_l1b",
                        "name": "INSAT-3DS L1B TIR1",
                        "status": "disabled",
                        "detail": "L1B off (MOSDAC_ALLOW_L1B=false); Himawari B13 used for Tb",
                    }
                )

        ingest_status.update(phase="cv", satellite={"id": "imerg", "status": "fetching"})
        try:
            imerg = await asyncio.wait_for(gpm_imerg.fetch_pin(22.07, 88.07, heavy=False), timeout=45)
            st = "ok" if imerg.get("ok") else imerg.get("status") or "fail"
            if imerg.get("eula"):
                st = "eula"
            ingest_status.update(
                satellite={
                    "id": "imerg",
                    "name": "GPM IMERG Early",
                    "status": st,
                    "detail": imerg.get("eula") or imerg.get("error") or imerg.get("status"),
                }
            )
        except Exception as e:
            detail = "timeout" if isinstance(e, asyncio.TimeoutError) else str(e)[:160]
            ingest_status.update(satellite={"id": "imerg", "status": "fail", "detail": detail})

        ingest_status.update(phase="predict", satellite={"id": "gibs", "status": "fetching"})
        try:
            from app.science import sat_lightning

            ltg = await asyncio.wait_for(sat_lightning.refresh(), timeout=45)
            from app.store import shared_packs

            await asyncio.to_thread(shared_packs.save_lightning, ltg)
        except Exception:
            pass
        await asyncio.sleep(0)
        from app.science.storm_map import build as build_storm_map

        pack = await asyncio.wait_for(build_storm_map("India", past_h=12), timeout=90)
        ingest_status.update(
            satellite={
                "id": "gibs",
                "name": "GIBS Himawari Band 13",
                "status": "ok" if (pack.get("sensors") or {}).get("gibs_ir") else "fail",
            }
        )
        ingest_status.update(phase="alerts")

        def _publish() -> None:
            from app.store import shared_packs, sat_mongo
            from app.store.hazard_events import slim_event
            from app.ingest.worker import record_slot_frame

            shared_packs.save_storm(pack)
            persist_pack_incidents(pack, cycle_id=cid)
            try:
                col = sat_mongo.col("alert_windows")
                if col is not None:
                    for inc in pack.get("incidents") or []:
                        if not (inc.get("gate") or {}).get("ok"):
                            continue
                        row = slim_event({**inc, "ingest_cycle_id": cid})
                        if row:
                            col.update_one({"event_id": row["event_id"]}, {"$set": row}, upsert=True)
            except Exception:
                pass
            prune_events()
            prune_frames()
            hem_time = next(
                (r.get("granule_time") for r in mosdac_rows if r.get("product") == "3SIMG_L2B_HEM" and r.get("ok")),
                None,
            )
            try:
                record_slot_frame(jpeg_time=jpeg_time if jpeg_ok else None, hem_time=hem_time)
            except Exception:
                pass

        await asyncio.to_thread(_publish)
        result["ok"] = bool(pack.get("ok") or jpeg_ok)
        result["counts"] = pack.get("counts")
        result["mosdac"] = mosdac_rows
        result["need_second_frame"] = pack.get("need_second_frame")
        data_time = jpeg_time or pack.get("ir_image_time") or pack.get("as_of")
        ingest_status.finish(ok=True, message="", data_time=str(data_time) if data_time else None)
        persisted = await asyncio.to_thread(ingest_status.persist_doc, ingest_status.mem_doc())
        print(
            f"ingest cycle finish cycle_id={cid} ok={result['ok']} persisted={persisted} counts={result.get('counts')} data_time={data_time}",
            flush=True,
        )
        log.info("ingest cycle ready cycle_id=%s ok=%s counts=%s", cid, result["ok"], result.get("counts"))
        return result
    except Exception as e:
        ingest_status.finish(ok=False, message=str(e)[:200])
        await asyncio.to_thread(ingest_status.persist_doc, ingest_status.mem_doc())
        result["error"] = str(e)[:200]
        print(f"ingest cycle error cycle_id={cid} err={result['error']}", flush=True)
        log.exception("ingest cycle error cycle_id=%s err=%s", cid, result["error"])
        return result

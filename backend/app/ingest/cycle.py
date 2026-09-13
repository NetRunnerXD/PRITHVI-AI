"""One ingest cycle: JPEG always, MOSDAC/Earthdata if new, then storm-map science."""

from __future__ import annotations

from typing import Any

from app.config import get_settings
from app.store import ingest_status
from app.store.hazard_events import persist_pack_incidents, prune as prune_events
from app.store.sat_frames import prune as prune_frames
from app.store.time import iso_z, now_utc

SATELLITES = (
    {"id": "imd_ir1", "name": "INSAT-3DS IR1 JPEG"},
    {"id": "mosdac_hem", "name": "INSAT-3DS HEM"},
    {"id": "mosdac_l1b", "name": "INSAT-3DS L1B TIR1"},
    {"id": "gibs", "name": "GIBS Himawari Band 13"},
    {"id": "imerg", "name": "GPM IMERG Early"},
)


async def run_cycle() -> dict[str, Any]:
    settings = get_settings()
    cid = ingest_status.begin(list(SATELLITES))
    now = now_utc()
    result: dict[str, Any] = {"cycle_id": cid, "as_of": iso_z(now), "ok": False}

    try:
        from app.providers import imd_insat, mosdac, gpm_imerg

        ingest_status.update(satellite={"id": "imd_ir1", "status": "fetching"})
        jpeg_ok = False
        try:
            body, _url, status = await imd_insat.fetch_jpeg()
            jpeg_ok = bool(body)
            ingest_status.update(
                satellite={"id": "imd_ir1", "name": "INSAT-3DS IR1 JPEG", "status": "ok" if jpeg_ok else "fail", "detail": status}
            )
        except Exception as e:
            ingest_status.update(satellite={"id": "imd_ir1", "status": "fail", "detail": str(e)[:160]})

        ingest_status.update(satellite={"id": "mosdac_hem", "status": "fetching"})
        mosdac_rows: list[dict[str, Any]] = []
        try:
            mosdac_rows = await mosdac.ingest_latest(allow_l1b=bool(settings.mosdac_allow_l1b))
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
                    "status": l1.get("status") or ("ok" if l1.get("ok") else "fail"),
                    "detail": l1.get("error") or l1.get("status"),
                }
            )
        except Exception as e:
            ingest_status.update(satellite={"id": "mosdac_hem", "status": "fail", "detail": str(e)[:160]})
            ingest_status.update(satellite={"id": "mosdac_l1b", "status": "fail"})

        ingest_status.update(phase="cv", satellite={"id": "imerg", "status": "fetching"})
        try:
            imerg = await gpm_imerg.fetch_pin(22.07, 88.07, heavy=False)
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
            ingest_status.update(satellite={"id": "imerg", "status": "fail", "detail": str(e)[:160]})

        ingest_status.update(phase="predict", satellite={"id": "gibs", "status": "fetching"})
        from app.science.storm_map import build as build_storm_map

        pack = await build_storm_map("India", past_h=12)
        ingest_status.update(
            satellite={
                "id": "gibs",
                "name": "GIBS Himawari Band 13",
                "status": "ok" if (pack.get("sensors") or {}).get("gibs_ir") else "fail",
            }
        )
        ingest_status.update(phase="alerts")
        persist_pack_incidents(pack, cycle_id=cid)
        try:
            from app.store import sat_mongo
            from app.store.hazard_events import slim_event

            col = sat_mongo.col("alert_windows")
            if col is not None:
                for inc in pack.get("incidents") or []:
                    if not (inc.get("gate") or {}).get("ok"):
                        continue
                    if inc.get("kind") == "lightning" and not (inc.get("gate") or {}).get("ok"):
                        continue
                    row = slim_event({**inc, "ingest_cycle_id": cid})
                    if row:
                        col.update_one({"event_id": row["event_id"]}, {"$set": row}, upsert=True)
        except Exception:
            pass
        prune_events()
        prune_frames()
        result["ok"] = bool(pack.get("ok") or jpeg_ok)
        result["counts"] = pack.get("counts")
        result["mosdac"] = mosdac_rows
        result["need_second_frame"] = pack.get("need_second_frame")
        ingest_status.finish(ok=True, message="")
        return result
    except Exception as e:
        ingest_status.finish(ok=False, message=str(e)[:200])
        result["error"] = str(e)[:200]
        return result

"""Delete unlabeled hazard/risk map records from Mongo.

A record is unlabeled if it has no usable kind, no coordinates, or no
place/title/label. Skill logs (lightning_verify) and titled CAP alerts
without lat/lon are left in place.

    python scripts/cleanup_unlabeled_mongo.py
"""

from __future__ import annotations

from pymongo import MongoClient

from app.config import get_settings

NAMED_EVENT = {
    "cloud",
    "cloudburst",
    "downburst",
    "fire",
    "landslide",
    "lightning",
    "storm",
}
NAMED_ALERT = {
    "cloudburst",
    "drought",
    "extreme_rain",
    "fire",
    "flood",
    "fog",
    "heatwave",
    "lightning",
    "marine",
    "rainfall",
    "seismic",
    "thunderstorm",
    "tsunami",
    "uv",
    "uv_heat",
    "wind",
    "cyclone",
    "aqi",
}


def blank(v) -> bool:
    return v is None or (isinstance(v, str) and not str(v).strip())


def unlabeled_map_doc(d: dict, named: set[str]) -> bool:
    kind = d.get("kind")
    if not isinstance(kind, str) or kind.strip() not in named:
        return True
    if d.get("lat") is None or d.get("lon") is None:
        return True
    try:
        float(d["lat"])
        float(d["lon"])
    except (TypeError, ValueError):
        return True
    if blank(d.get("place")) and blank(d.get("title")) and blank(d.get("label")):
        return True
    return False


def purge_col(col, named: set[str], *, require_coords: bool) -> dict:
    ids = []
    for d in col.find({}):
        if require_coords:
            if unlabeled_map_doc(d, named):
                ids.append(d["_id"])
        else:
            kind = d.get("kind")
            if not isinstance(kind, str) or kind.strip() not in named:
                ids.append(d["_id"])
            elif blank(d.get("title")) and blank(d.get("place")) and blank(d.get("label")):
                ids.append(d["_id"])
    n = 0
    if ids:
        n = col.delete_many({"_id": {"$in": ids}}).deleted_count
    return {"scanned": col.estimated_document_count() + n, "deleted": n}


def clean_nested_cells(col, named: set[str]) -> dict:
    rewritten = 0
    dropped_cells = 0
    dropped_docs = 0
    for fr in list(col.find({})):
        cells = fr.get("cells") or []
        if not isinstance(cells, list):
            col.delete_one({"_id": fr["_id"]})
            dropped_docs += 1
            continue
        keep = [c for c in cells if isinstance(c, dict) and not unlabeled_map_doc(c, named)]
        dropped_cells += len(cells) - len(keep)
        if not keep:
            col.delete_one({"_id": fr["_id"]})
            dropped_docs += 1
        elif dropped_cells:
            col.update_one({"_id": fr["_id"]}, {"$set": {"cells": keep, "n": len(keep)}})
            rewritten += 1
    return {"rewritten": rewritten, "dropped_cells": dropped_cells, "dropped_docs": dropped_docs}


def main() -> None:
    s = get_settings()
    sat = MongoClient(s.mongodb_sat_uri, serverSelectionTimeoutMS=12000)
    acct = MongoClient(s.mongodb_uri, serverSelectionTimeoutMS=12000)
    report = {}

    report["sat.hazard_events"] = purge_col(sat["rituchakra_sat"]["hazard_events"], NAMED_EVENT, require_coords=True)
    report["sat.alert_windows"] = purge_col(sat["rituchakra_sat"]["alert_windows"], NAMED_EVENT | NAMED_ALERT, require_coords=True)
    report["acct.storm_cells"] = purge_col(acct["rituchakra"]["storm_cells"], NAMED_EVENT, require_coords=True)
    # Alerts with titles but no lat/lon stay; drop only blank-title/kind rows.
    report["acct.hazard_events"] = purge_col(acct["rituchakra"]["hazard_events"], NAMED_ALERT, require_coords=False)
    report["acct.ir_frames"] = clean_nested_cells(acct["rituchakra"]["ir_frames"], NAMED_EVENT)
    report["sat.ir_frames"] = clean_nested_cells(sat["rituchakra_sat"]["ir_frames"], NAMED_EVENT)

    leftover_sat = sat["rituchakra_sat"]["hazard_events"].count_documents(
        {"$or": [{"place": None}, {"place": ""}, {"kind": None}, {"kind": ""}]}
    )
    leftover_cells = acct["rituchakra"]["storm_cells"].count_documents(
        {"$or": [{"place": None}, {"place": ""}, {"kind": None}, {"kind": ""}]}
    )
    print({"report": report, "leftover_sat_unlabeled": leftover_sat, "leftover_storm_cells_unlabeled": leftover_cells})
    sat.close()
    acct.close()


if __name__ == "__main__":
    main()

"""Audit unlabeled hazard/risk documents. Run: python scripts/audit_unlabeled_mongo.py"""

from __future__ import annotations

from collections import Counter

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


def kind_ok(kind, named: set[str]) -> bool:
    return isinstance(kind, str) and kind.strip() in named


def unlabeled_event(d: dict, named: set[str]) -> str | None:
    if not kind_ok(d.get("kind"), named):
        return "bad_kind"
    if d.get("lat") is None or d.get("lon") is None:
        return "no_coords"
    try:
        float(d["lat"])
        float(d["lon"])
    except (TypeError, ValueError):
        return "bad_coords"
    if blank(d.get("place")) and blank(d.get("title")) and blank(d.get("label")):
        return "no_place_title_label"
    return None


def scan_col(col, named: set[str], extra_title: bool = False) -> dict:
    reasons: Counter[str] = Counter()
    kinds: Counter[str] = Counter()
    n = 0
    ids = []
    for d in col.find({}):
        n += 1
        kinds[repr(d.get("kind"))] += 1
        why = unlabeled_event(d, named)
        if extra_title and blank(d.get("title")) and blank(d.get("place")):
            why = why or "no_title"
        if why:
            reasons[why] += 1
            ids.append(d.get("_id"))
    return {"n": n, "bad": len(ids), "reasons": dict(reasons), "kinds": dict(kinds), "ids": ids}


def nested_cells(cells, named) -> tuple[int, int]:
    bad = 0
    for x in cells or []:
        if not isinstance(x, dict):
            bad += 1
            continue
        if unlabeled_event(x, named):
            bad += 1
    return len(cells or []), bad


def main() -> None:
    s = get_settings()
    sat = MongoClient(s.mongodb_sat_uri, serverSelectionTimeoutMS=8000)
    acct = MongoClient(s.mongodb_uri, serverSelectionTimeoutMS=8000)

    print("=== rituchakra_sat.hazard_events ===")
    r = scan_col(sat["rituchakra_sat"]["hazard_events"], NAMED_EVENT)
    print({k: r[k] for k in ("n", "bad", "reasons", "kinds")})

    print("=== rituchakra.hazard_events ===")
    r2 = scan_col(acct["rituchakra"]["hazard_events"], NAMED_ALERT, extra_title=True)
    print({k: r2[k] for k in ("n", "bad", "reasons", "kinds")})

    print("=== rituchakra.storm_cells ===")
    r3 = scan_col(acct["rituchakra"]["storm_cells"], NAMED_EVENT)
    print({k: r3[k] for k in ("n", "bad", "reasons", "kinds")})

    print("=== rituchakra.lightning_verify ===")
    r4 = scan_col(acct["rituchakra"]["lightning_verify"], NAMED_EVENT)
    print({k: r4[k] for k in ("n", "bad", "reasons", "kinds")})

    rm = acct["rituchakra"]["risk_mesh"]
    print("=== rituchakra.risk_mesh ===")
    n_rm = rm.count_documents({})
    bad_rm = list(rm.find({"$or": [{"state": None}, {"state": ""}, {"hq": None}, {"hq": ""}]}))
    print("n", n_rm, "no_state_or_hq", len(bad_rm))

    print("=== rituchakra.ir_frames nested ===")
    for fr in acct["rituchakra"]["ir_frames"].find():
        tot, bad = nested_cells(fr.get("cells") or [], NAMED_EVENT)
        print(" frame", fr.get("t"), "n", tot, "unlabeled", bad)

    print("=== rituchakra.storm_map_pack nested ===")
    for p in acct["rituchakra"]["storm_map_pack"].find():
        pack = p.get("_pack") if isinstance(p.get("_pack"), dict) else p
        for key in (
            "polygons",
            "cells",
            "incidents",
            "predicted",
            "predicted_storms",
            "predicted_unverified",
            "past_cells",
            "strokes",
            "fires",
            "landslides",
        ):
            rows = pack.get(key) or []
            if not isinstance(rows, list) or not rows:
                continue
            tot, bad = nested_cells(rows, NAMED_EVENT | NAMED_ALERT | {"lightning"})
            print(" ", p.get("state"), key, "n", tot, "unlabeled", bad)

    print("=== sat.alert_windows / sat_frames ===")
    print("alert_windows", sat["rituchakra_sat"]["alert_windows"].count_documents({}))
    print("sat_frames", sat["rituchakra_sat"]["sat_frames"].count_documents({}))

    print("=== sat.hazard_events place quality ===")
    places = sat["rituchakra_sat"]["hazard_events"].distinct("place")
    coordish = []
    for p in places:
        s = str(p or "")
        if not s.strip() or s.lower() in {"none", "unknown", "n/a", "null"}:
            coordish.append(p)
            continue
        # "22.57, 88.36" style
        parts = s.replace("°", "").split(",")
        if len(parts) == 2:
            try:
                float(parts[0].strip())
                float(parts[1].strip())
                coordish.append(p)
            except ValueError:
                pass
    print(" distinct places", len(places), "coord-or-blank", len(coordish), "samples", coordish[:15])
    n_coord_place = sat["rituchakra_sat"]["hazard_events"].count_documents({"place": {"$in": coordish}}) if coordish else 0
    print(" docs with coord-only place", n_coord_place)

    print("=== rituchakra.hazard_events no coords sample ===")
    for d in acct["rituchakra"]["hazard_events"].find({"$or": [{"lat": None}, {"lat": {"$exists": False}}]}).limit(5):
        print(" ", {k: d.get(k) for k in ("kind", "title", "source", "states", "lat", "lon")})

    print("=== ir_frames unlabeled cell sample ===")
    for fr in acct["rituchakra"]["ir_frames"].find():
        cells = fr.get("cells") or []
        bad = [x for x in cells if isinstance(x, dict) and unlabeled_event(x, NAMED_EVENT)]
        if bad:
            print(" frame", fr.get("t"), "example", {k: bad[0].get(k) for k in ("kind", "place", "lat", "lon", "id")})

    print("=== storm_map_pack keys ===")
    for p in acct["rituchakra"]["storm_map_pack"].find():
        print(" top", sorted(p.keys()))
        pack = p.get("_pack") if isinstance(p.get("_pack"), dict) else {}
        print(" _pack keys", sorted(pack.keys())[:40] if pack else None)
        inner = pack or p
        for key in ("polygons", "cells", "incidents", "predicted", "predicted_storms"):
            rows = inner.get(key) or []
            print("  ", key, type(rows), len(rows) if isinstance(rows, list) else rows)

    sat.close()
    acct.close()


if __name__ == "__main__":
    main()

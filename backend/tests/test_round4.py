"""Round 4: GFS world grid packing, JTWC parsing + cone, verification badges."""

from __future__ import annotations

import io
from datetime import datetime, timedelta, timezone

import numpy as np

UTC = timezone.utc


def test_gfs_regrid_and_quant_png():
    from PIL import Image

    from app.providers import gfs

    lat = np.linspace(90, -90, 361)[:, None] * np.ones((1, 720))
    lon = np.ones((361, 1)) * np.arange(0, 360, 0.5)[None, :]
    a = gfs._to_1deg(lat)
    assert a.shape == (gfs.NY, gfs.NX)
    assert a[0, 0] == -80 and a[-1, 0] == 80  # ascending latitude
    b = gfs._to_1deg(lon)
    assert b[0, 0] == 180 and b[0, 180] == 0  # lon -180 (=180E) ... 0 at column 180
    q = gfs._quant("temp_c", np.array([-60.0, 0.0, 50.0, np.nan]))
    assert list(q) == [0, 128, 255, 0]
    pr = gfs._quant("precip_mm", np.array([0.0, 100.0]))
    assert list(pr) == [0, 255]
    gfs._STATE["fields"] = {3: {"temp_c": gfs._quant("temp_c", a.astype(float) / 2)}}
    blob = gfs.png("temp_c", 3)
    img = np.asarray(Image.open(io.BytesIO(blob)))
    assert img.shape == (gfs.NY, gfs.NX)
    assert img[0, 0] > img[-1, 0]  # row 0 = north (warmer in this synthetic ramp)
    gfs._STATE["fields"] = None


TCW = """WTPN52 PGTW 200300
WARNING    ATCG MIL 29W NWP 261020015130
2026102000 29W CHAMPI     023  01 295 12 SATL 010
T000 159N 1356E 130 R064 100 NE QD
T012 170N 1331E 130
T024 181N 1307E 145
AMP
SUBJ:  SUPER TYPHOON 29W (CHAMPI) WARNING NR 023
2926101900 140N1392E 135
2926101906 143N1384E 140
2926101906 143N1384E 140
2926102000 159N1356E 130
NNNN
"""


def test_jtwc_tcw_parse_and_cone():
    from app.providers import cyclones

    j = cyclones.parse_tcw(TCW)
    assert j["id"] == "29W" and j["name"] == "Champi"
    assert [p["h"] for p in j["forecast"]] == [0, 12, 24]
    assert j["forecast"][1]["lat"] == 17.0 and j["forecast"][1]["lon"] == 133.1
    assert len(j["observed"]) == 3  # duplicates collapsed
    assert j["observed"][-1]["t"] == "2026-10-20T00:00:00Z"
    cone = cyclones.cone_polygon([{"h": 0, **j["forecast"][0]}] + j["forecast"][1:])
    ring = cone["coordinates"][0]
    assert ring[0] == ring[-1] and len(ring) > 6
    assert cyclones.parse_tcw("ALERT ATCF MIL 93X\n2026101918\n") is None


def test_verify_live_badge_and_landslide(tmp_path, monkeypatch):
    from app.science import verify_items

    monkeypatch.setattr(verify_items, "_path", lambda: tmp_path / "v.json")
    monkeypatch.setattr(verify_items, "_LOG", None)
    monkeypatch.setattr(verify_items, "kick", lambda todo: None)
    from app.providers import gibs_ir

    now = datetime(2026, 10, 20, 3, 0, tzinfo=UTC)
    tb = np.full((10, 10), 280.0)
    monkeypatch.setattr(gibs_ir, "tb_at", lambda grid, lat, lon, half_deg=0.15: 220.0 if lat > 20 else 270.0)
    htb = {"ok": True, "tb": tb, "valid": (now - timedelta(minutes=20)).isoformat()}
    pack = {
        "cell_source": "insat-3ds-ir1",
        "incidents": [
            {"kind": "storm", "phase": "live", "lat": 25.0, "lon": 80.0, "started_ms": int(now.timestamp() * 1000)},
            {"kind": "lightning", "phase": "live", "lat": 15.0, "lon": 78.0, "started_ms": int(now.timestamp() * 1000)},
            {"kind": "storm", "phase": "past", "lat": 22.0, "lon": 77.0, "occurred_at": (now - timedelta(hours=2)).isoformat()},
        ],
        "landslides": [{"lat": 30.0, "lon": 79.0, "phase": "live"}],
    }
    verify_items.attach(pack, htb, now)
    st = [i["verification"]["status"] for i in pack["incidents"]]
    assert st == ["verified", "not_verified", "pending"]
    assert pack["incidents"][0]["verification"]["by"] == "Himawari B13"
    assert pack["landslides"][0]["verification"]["status"] == "not_verified"
    assert pack["verification_24h"]["storms"]["verified"] == 1
    assert pack["verification_24h"]["lightning"]["not_verified"] == 1
    # Himawari-derived cells cannot verify themselves.
    pack2 = {"cell_source": "himawari9-b13", "incidents": [{"kind": "storm", "phase": "live", "lat": 25.0, "lon": 80.0}]}
    verify_items.attach(pack2, htb, now)
    assert pack2["incidents"][0]["verification"]["status"] == "pending"
    # Stale Himawari frame (> 60 min away) -> pending, never verified.
    old = {**htb, "valid": (now - timedelta(hours=3)).isoformat()}
    pack3 = {"cell_source": "insat-3ds-ir1", "incidents": [{"kind": "storm", "phase": "live", "lat": 25.0, "lon": 80.0, "started_ms": int(now.timestamp() * 1000)}]}
    verify_items.attach(pack3, old, now)
    assert pack3["incidents"][0]["verification"]["status"] == "pending"

"""Round-3: alert windows, gov CA trust, slim dashboard, embedded ingest mode."""

from __future__ import annotations

import ssl
from datetime import datetime, timedelta, timezone

from app.schemas.dashboard import EarlyWarning

IST = timezone(timedelta(hours=5, minutes=30))


def _w(**kw):
    base = dict(id="x", kind="rain", severity="watch", title="t", body="b", source="s")
    base.update(kw)
    return EarlyWarning(**base)


def test_finalize_windows_drops_expired_and_infers_end():
    from app.services.alerts import finalize_windows

    now = datetime.now(IST)
    expired = _w(id="old", window_start=(now - timedelta(hours=10)).isoformat(), window_end=(now - timedelta(hours=1)).isoformat())
    active = _w(id="act", window_start=(now - timedelta(hours=1)).isoformat(), window_end=(now + timedelta(hours=2)).isoformat())
    upcoming = _w(id="up", window_start=(now + timedelta(hours=3)).isoformat(), window_end=(now + timedelta(hours=5)).isoformat())
    open_end = _w(id="noend", kind="cyclone", issued_at=(now - timedelta(hours=2)).isoformat())
    stale_open = _w(id="stale", kind="fire", issued_at=(now - timedelta(hours=40)).isoformat())
    out = {w.id: w for w in finalize_windows([expired, active, upcoming, open_end, stale_open])}
    assert "old" not in out and "stale" not in out
    assert out["act"].status == "active"
    assert out["up"].status == "upcoming"
    assert out["noend"].end_inferred is True and out["noend"].window_end


def test_gov_ssl_context_trusts_emsign():
    from app.providers import http

    ctx = http._gov_ssl_context()
    assert isinstance(ctx, ssl.SSLContext)
    subjects = {str(dict(x[0] for x in c["subject"]).get("commonName")) for c in ctx.get_ca_certs()}
    assert any("emSign Root CA - G1" in s for s in subjects)
    assert http._is_gov("sachet.ndma.gov.in") and http._is_gov("mausam.imd.gov.in")
    assert not http._is_gov("api.open-meteo.com")


def test_slim_dump_drops_heavy_vera():
    from app.services.snapshot import slim_dump

    class Snap:
        def model_dump(self, **_):
            return {
                "predictions": {"vera": {"intra_hour": [1] * 100, "hourly": [1], "headline": "keep"}},
                "science": {"nowcast": {"grid": [[1]], "frames": [1], "summary": "keep"}},
            }

    d = slim_dump(Snap())
    assert d["predictions"]["vera"]["intra_hour"] is None
    assert d["predictions"]["vera"]["headline"] == "keep"
    assert d["science"]["nowcast"]["summary"] == "keep"
    assert d.get("slim") is True


def test_embedded_ingest_mode(monkeypatch):
    from app.ingest import worker

    monkeypatch.delenv("INGEST_EMBEDDED", raising=False)
    assert worker.embedded_mode() == "auto"
    monkeypatch.setenv("INGEST_EMBEDDED", "0")
    assert worker.embedded_mode() == "off"
    monkeypatch.setenv("INGEST_INTERVAL_S", "5")
    assert worker.interval_s() == 60


def test_pn_live_ascii_parser_orientation():
    import numpy as np

    from app.science.pn import live

    rows = [f"precipitation[0][{j}], " + ", ".join(str(round(j * 1.0 + i / 1000, 4)) for i in range(live.H)) for j in range(live.W)]
    a = live._parse_ascii("Dataset: x.HDF5\n" + "\n".join(rows))
    assert a is not None and a.shape == (live.H, live.W)
    assert abs(a[5, 7] - (7 + 5 / 1000)) < 1e-4  # [lat, lon], south row first
    assert np.isnan(live._parse_ascii("\n".join(rows).replace("precipitation[0][0], 0.0,", "precipitation[0][0], -9999.9,"))[0, 0])


def test_sat_lightning_rule_and_gate():
    import numpy as np

    from app.science import sat_lightning as sl

    tb = np.full((20, 20), 290.0, np.float32)
    tb[8:13, 8:13] = 205.0  # cold core
    prev = tb.copy()
    prev[8:13, 8:13] = 230.0  # 25 K colder in 20 min → cooling
    sc = sl.score(tb, prev, 20.0)
    assert sc["p"][10, 10] >= 0.6 + 0.25 - 1e-6
    assert sc["p"][0, 0] == 0.0
    # no previous data must not look like cooling
    sc2 = sl.score(tb, np.full_like(tb, np.nan), 20.0)
    assert np.isnan(sc2["cool"][10, 10])
    assert sl._gate(0.9, 0.0, 5.0) < 0.3  # stable column suppressed below 'possible'
    assert sl._gate(0.5, 1500.0, -3.0) > 0.5


def test_grey_palette_ambiguity_reads_warm_in_clear_sky():
    import numpy as np

    from app.providers import gibs_ir

    lut = gibs_ir._lut("ir_c")
    warm = next(k for k, v in lut.items() if v is not None and k[0] == k[1] == k[2] and v + 273.15 > 285)
    arr = np.zeros((9, 9, 4), np.uint8)
    arr[...] = (*warm, 255)
    arr[4, 4] = (102, 102, 102, 255)  # exact entry for 198.5 K in the cold grey band
    tb = gibs_ir._tb_full(arr)
    assert tb[4, 4] > 260  # re-read on the warm ramp, not a fake overshooting top

from app.ml.vera.historical import analogue_search, climatology, embedding, run, spatial_patterns


def test_clim_and_analogues():
    series = [float(i % 40) for i in range(200)]
    clim = climatology(series, 200)
    assert clim["p95"] >= clim["p50"]
    cat = [{"mm": 40.0, "date": "2019-07-01"}, {"mm": 12.0, "date": "2018-06-01"}]
    an = analogue_search(0.5, 38.0, 4, cat)
    assert an[0]["mm"] == 40.0


def test_embedding_len():
    emb = embedding({"mean": 6, "std": 4, "p95": 30, "harmonic_doy": 7}, [], {"onset_doy": 160, "iso_phase": 3}, spatial_patterns(22.0, 88.0))
    assert len(emb) == 64


def test_run_fill():
    pack = run({"clim_daily_mm": 8.0, "precip_z": 1.0, "precip_3d_mm": 20, "daily_times": ["2026-07-15"]}, 22.5, 88.3, {"indices": {"mjo_phase_proxy": 4, "monsoon_clock": "active"}, "top": "active_monsoon"})
    assert pack["temporal_resolution"] == "daily"
    assert pack["climatology"]["mean"] >= 0

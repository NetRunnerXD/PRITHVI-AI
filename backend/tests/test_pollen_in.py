from app.science.pollen_in import estimate
from app.providers.hazards import _merge_quakes
from app.services.snapshot import _quake_display


def test_india_pollen_has_seasonal_grains_not_zero():
    pack = estimate(22.07, 88.07, {"precip_now": 0, "wind_now": 10})
    assert pack["grass"] >= 0.5
    assert pack["mugwort"] >= 0.5
    assert pack["ragweed"] >= 0.5
    assert pack["alder"] >= 0.5
    assert pack["birch"] >= 0.5
    assert pack["olive"] >= 0.5
    assert "climatology" in pack["source"].lower()


def test_quake_display_prefers_usgs_with_nst():
    rows = [
        {"mag": 3.2, "nst": None, "gap": None, "distance_km": 80, "source": "EMSC FDSN", "place": "near"},
        {"mag": 4.0, "nst": 21, "gap": 176, "distance_km": 400, "source": "USGS FDSN (India–Indian Ocean box; NCS has no public JSON)", "place": "Sarahan"},
    ]
    pick = _quake_display(rows)
    assert pick["nst"] == 21
    assert pick["mag"] == 4.0


def test_merge_quakes_still_dedupes():
    a = [{"mag": 5.1, "time_iso": "t1", "place": "Andaman", "magType": "mb"}]
    b = [{"mag": 5.1, "time_iso": "t1", "place": "Andaman", "source": "EMSC"}]
    assert len(_merge_quakes(a, b)) == 1

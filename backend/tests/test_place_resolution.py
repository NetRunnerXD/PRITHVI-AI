"""resolve_named_place never falls back to Haldia; DataLib rejects unknown names."""

import pytest

from app.agents.data_tool import DataLib
from app.schemas.location import Location
from app.services.location_svc import resolve_location, resolve_named_place


def _pin() -> Location:
    return resolve_location(q="Haldia")


@pytest.mark.asyncio
async def test_tomorrow_does_not_geocode():
    from app.services.location_svc import resolve_india_place, resolve_named_place

    assert resolve_named_place("tomorrow") is None
    assert resolve_named_place("today") is None
    assert await resolve_india_place("tomorrow") is None
    assert await resolve_india_place("and tomorrow") is None


def test_unknown_does_not_become_haldia():
    assert resolve_named_place("Atlantis") is None
    assert resolve_named_place("Hogwarts") is None
    assert resolve_named_place("") is None
    fallback = resolve_location()
    assert fallback.place_name == "Haldia"


def test_indic_aliases_resolve_nadia_and_howrah():
    from app.data.india_districts import extract_place

    assert extract_place("নদিয়ায় আগামী ৩ দিনে কত বৃষ্টি?") == "Nadia"
    assert extract_place("हावड़ा में आज मौसम कैसा है?") == "Howrah"


def test_named_beats_default_pin():
    loc = resolve_named_place("Puruliya")
    assert loc is not None
    assert loc.district == "Purulia"
    assert loc.place_name != "Haldia"
    assert abs(loc.lat - 23.3321) < 0.2


def test_state_name_resolves_to_capital():
    od = resolve_named_place("Odisha")
    assert od is not None
    assert od.place_name == "Bhubaneswar"
    assert od.district == "Khordha"
    wb = resolve_named_place("West Bengal")
    assert wb is not None
    assert wb.place_name == "Kolkata"
    assert wb.label != "West Bengal, West Bengal"


@pytest.mark.asyncio
async def test_data_lib_unknown_place_error():
    lib = DataLib(_pin())
    out = await lib.call({"need": "forecast", "place": "Atlantis"})
    assert out.get("error") == "unknown_place"
    assert out.get("place") == "Atlantis"
    assert lib.loc.place_name == "Haldia"


@pytest.mark.asyncio
async def test_data_lib_puruliya_switches_location(monkeypatch):
    lib = DataLib(_pin())

    async def fake_snap(self, loc=None):
        target = loc or self.loc
        class S:
            location = target
            predictive = type("P", (), {"model_dump": lambda self: {"precip_next_3d_mm": 9.0, "precip_7d_mm": 11.0}})()
            descriptive = type("D", (), {"current": type("C", (), {"temp_c": 29.1, "precip_1h_mm": 0.0, "sky_label": "clear"})()})()
        return S()

    monkeypatch.setattr(DataLib, "_snap", fake_snap)
    out = await lib.call({"need": "forecast", "place": "Puruliya"})
    assert out.get("error") != "unknown_place"
    assert lib.loc.district == "Purulia"
    assert "Puri" not in (out.get("label") or "")
    assert "Haldia" not in (out.get("label") or "")

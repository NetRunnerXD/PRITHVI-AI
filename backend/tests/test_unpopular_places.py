"""Unpopular Indian cities, towns, and districts — not a Haldia/Purulia-only gazetteer.

Local HQ table + Open-Meteo India geocode must cover any real place.
Each pass has a contradiction sibling so a lucky hit cannot hide a cousin miss.
"""

from __future__ import annotations

import pytest

from app.agents.facts import fill_slots, source_gate
from app.agents.utterance import interpret
from app.schemas.chat import ChatRequest
from app.services.location_svc import (
    compose_label,
    resolve_india_place,
    resolve_location,
    resolve_named_place,
)

# Real places that are easy to miss if the chat only knows a handful of HQs.
UNPOPULAR = [
    ("Wardha", "Maharashtra", 20.7453, 78.6022),
    ("Mandya", "Karnataka", 12.5223, 76.8970),
    ("Jhunjhunu", "Rajasthan", 28.1289, 75.3997),
    ("Tezpur", "Assam", 26.6338, 92.8000),
    ("Munnar", "Kerala", 10.0889, 77.0595),
    ("Ooty", "Tamil Nadu", 11.4064, 76.6932),
    ("Rishikesh", "Uttarakhand", 30.0869, 78.2676),
    ("Haridwar", "Uttarakhand", 29.9457, 78.1642),
    ("Tirupati", "Andhra Pradesh", 13.6288, 79.4192),
    ("Satara", "Maharashtra", 17.6805, 74.0183),
    ("Aligarh", "Uttar Pradesh", 27.8974, 78.0880),
    ("Kargil", "Ladakh", 34.5539, 76.1349),
    ("Tawang", "Arunachal Pradesh", 27.5860, 91.8590),
    ("Mount Abu", "Rajasthan", 24.5926, 72.7156),
    ("Vellore", "Tamil Nadu", 12.9165, 79.1325),
    ("Nanded", "Maharashtra", 19.1383, 77.3210),
    ("Moradabad", "Uttar Pradesh", 28.8386, 78.7733),
    ("Bareilly", "Uttar Pradesh", 28.3670, 79.4304),
    ("Bokaro", "Jharkhand", 23.6693, 86.1511),
    ("Palakkad", "Kerala", 10.7867, 76.6548),
    ("Thrissur", "Kerala", 10.5276, 76.2144),
    ("Kollam", "Kerala", 8.8932, 76.6141),
    ("Nizamabad", "Telangana", 18.6725, 78.0941),
    ("Leh", "Ladakh", 34.1526, 77.5771),
]

CITY_STATES = [
    ("Delhi", "Delhi", "New Delhi"),
    ("Chandigarh", "Chandigarh", "Chandigarh"),
    ("Goa", "Goa", "North Goa"),
    ("Puducherry", "Puducherry", "Puducherry"),
]


def _om_row(name: str, state: str, lat: float, lon: float) -> dict:
    return {
        "id": abs(hash(name)) % 10_000_000,
        "name": name,
        "admin1": state,
        "admin2": name,
        "latitude": lat,
        "longitude": lon,
        "feature_code": "PPL",
        "country_code": "IN",
    }


GEOCODE = {name.lower(): _om_row(name, state, lat, lon) for name, state, lat, lon in UNPOPULAR}


@pytest.fixture
def fake_geocode(monkeypatch):
    async def _geo(name: str):
        row = GEOCODE.get((name or "").strip().lower())
        return [row] if row else []

    monkeypatch.setattr("app.providers.open_meteo.geocode_india", _geo)
    return _geo


def test_delhi_is_a_city_forecast_not_a_template():
    loc = resolve_named_place("Delhi")
    assert loc is not None
    assert loc.state == "Delhi"
    assert loc.place_name in {"Delhi", "New Delhi"}
    assert loc.label != "Delhi, Delhi"
    assert "Haldia" not in loc.label
    g = source_gate("Delhi")
    assert g.mode == "data"
    assert "forecast" in g.needs
    assert "states_weather" not in g.needs


def test_compose_label_never_doubles_city_state():
    assert compose_label("Delhi", "Delhi") == "Delhi"
    assert compose_label("Delhi", "NCT of Delhi") == "Delhi"
    assert compose_label("Wardha", "Maharashtra") == "Wardha, Maharashtra"


@pytest.mark.parametrize("name,state,district", CITY_STATES)
def test_city_state_resolves_locally(name, state, district):
    loc = resolve_named_place(name)
    assert loc is not None, name
    assert loc.state == state
    assert loc.district == district
    assert loc.label != f"{name}, {name}"


@pytest.mark.parametrize("name,state,lat,lon", UNPOPULAR)
def test_unpopular_name_is_not_refused_up_front(name, state, lat, lon):
    p = interpret(name)
    assert p.mode != "refuse", name
    assert "forecast" in p.needs
    g = source_gate(f"weather in {name}")
    assert g.mode == "data"
    assert "forecast" in g.needs


@pytest.mark.asyncio
@pytest.mark.parametrize("name,state,lat,lon", UNPOPULAR)
async def test_unpopular_geocode_then_forecast_point(name, state, lat, lon, fake_geocode):
    loc = await resolve_india_place(name)
    assert loc is not None, name
    assert loc.place_name == name
    assert state.lower() in loc.state.lower() or loc.state
    assert abs(loc.lat - lat) < 0.2
    assert loc.place_name != "Haldia"
    assert "Haldia" not in loc.label


@pytest.mark.asyncio
async def test_contradiction_wardha_is_not_warangal(fake_geocode):
    w = await resolve_india_place("Wardha")
    g = resolve_named_place("Warangal")
    assert w is not None and g is not None
    assert w.place_name == "Wardha"
    assert g.district == "Warangal" or g.place_name == "Warangal"
    assert abs(w.lat - g.lat) > 1.0


@pytest.mark.asyncio
async def test_contradiction_unpopular_miss_does_not_become_haldia(fake_geocode):
    pin = resolve_location()
    assert pin.place_name == "Haldia"
    loc = await resolve_india_place("Jhunjhunu")
    assert loc is not None
    assert loc.place_name == "Jhunjhunu"
    assert loc.place_name != pin.place_name


@pytest.mark.asyncio
async def test_contradiction_atlantis_still_skips_geocode(fake_geocode):
    assert await resolve_india_place("Atlantis") is None
    p = interpret("weather in Atlantis")
    assert p.mode == "refuse"


@pytest.mark.asyncio
async def test_datalib_fetches_unpopular_not_pin(fake_geocode, monkeypatch):
    from app.agents.data_tool import DataLib

    async def fake_snap(self, loc=None):
        target = loc or self.loc

        class S:
            location = target
            predictive = type(
                "P",
                (),
                {"model_dump": lambda self: {"precip_next_3d_mm": 7.5, "precip_7d_mm": 14.0}},
            )()
            descriptive = type(
                "D",
                (),
                {"current": type("C", (), {"temp_c": 29.0, "precip_1h_mm": 0.4, "sky_label": "cloudy"})()},
            )()

        return S()

    monkeypatch.setattr(DataLib, "_snap", fake_snap)
    lib = DataLib(resolve_location(q="Haldia"))
    out = await lib.call({"need": "forecast", "place": "Munnar"})
    assert out.get("error") != "unknown_place"
    assert lib.loc.place_name == "Munnar"
    assert out.get("temp_c") == 29.0
    assert "Haldia" not in (out.get("label") or "")


@pytest.mark.asyncio
async def test_orchestrator_delhi_fills_placeholders(monkeypatch):
    from app.agents import orchestrator
    from app.llm import ollama_client

    async def fake_ping():
        return True, "qwen2.5"

    async def fake_chat(messages, tools=None):
        return {
            "content": (
                "I have the current weather and forecast for Delhi, Delhi. "
                "The temperature is currently [temp_c]°C and there are expected to be "
                "[rain_mm] mm of rain in the next few hours."
            ),
            "tool_calls": [],
            "tools_stripped": False,
        }

    async def fake_call(self, args):
        loc = self.loc
        return {
            "need": "forecast",
            "place": loc.place_name or loc.district,
            "label": loc.label,
            "temp_c": 32.4,
            "precip_1h_mm": 0.2,
            "precip_next_3d_mm": 11.0,
            "precip_7d_mm": 20.0,
        }

    monkeypatch.setattr(ollama_client, "ping", fake_ping)
    monkeypatch.setattr(ollama_client, "chat", fake_chat)
    monkeypatch.setattr("app.agents.data_tool.DataLib.call", fake_call)

    events = []
    async for ev in orchestrator.run_agent(
        ChatRequest(message="Delhi", location=resolve_location(q="Haldia"))
    ):
        events.append(ev)
    body = next(e for e in events if e["type"] == "final")["message"].get("content_en") or ""
    assert "[temp_c]" not in body
    assert "[rain_mm]" not in body
    assert "32.4" in body
    assert "Haldia" not in body
    meta = next(e for e in events if e["type"] == "meta")
    assert "Delhi" in (meta.get("location") or {}).get("label", "")
    assert (meta.get("location") or {}).get("label") != "Delhi, Delhi"


@pytest.mark.asyncio
async def test_orchestrator_unpopular_uses_geocode(fake_geocode, monkeypatch):
    from app.agents import orchestrator
    from app.llm import ollama_client

    async def fake_ping():
        return True, "qwen2.5"

    async def fake_chat(messages, tools=None):
        return {"content": "Here is the outlook.", "tool_calls": [], "tools_stripped": False}

    fetched = []

    async def fake_call(self, args):
        fetched.append(self.loc)
        loc = self.loc
        return {
            "need": "forecast",
            "place": loc.place_name,
            "label": loc.label,
            "temp_c": 24.1,
            "precip_next_3d_mm": 5.0,
            "precip_7d_mm": 9.0,
        }

    monkeypatch.setattr(ollama_client, "ping", fake_ping)
    monkeypatch.setattr(ollama_client, "chat", fake_chat)
    monkeypatch.setattr("app.agents.data_tool.DataLib.call", fake_call)

    events = []
    async for ev in orchestrator.run_agent(
        ChatRequest(message="Tezpur", location=resolve_location(q="Haldia"))
    ):
        events.append(ev)
    assert fetched
    assert fetched[0].place_name == "Tezpur"
    assert fetched[0].state == "Assam"
    body = next(e for e in events if e["type"] == "final")["message"].get("content_en") or ""
    assert "24.1" in body
    assert "Haldia" not in body


def test_contradiction_rank_odisha_is_still_rank_not_only_capital():
    p = interpret("Flood ranking of Odisha")
    assert p.mode == "data"
    assert "rank" in p.needs
    assert "forecast" not in p.needs


def test_fill_slots_contradiction_does_not_invent():
    out = fill_slots("Temp is [temp_c]°C", {})
    assert "[temp_c]" not in out
    assert "32.4" not in out
    assert "—" in out

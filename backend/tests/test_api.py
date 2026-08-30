from fastapi.testclient import TestClient

from app.main import app
from app.services.location_svc import search

client = TestClient(app)


def test_health():
    r = client.get("/api/health")
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True
    assert "llm" in body
    assert body["llm"]["active"]
    assert any(r.get("id") == "ollama" for r in body["llm"]["available"])
    assert body["default_location"]["place_name"] == "Haldia"
    assert body["default_location"]["district"] == "Purba Medinipur"


def test_geo_reverse_rejects_outside_india():
    r = client.get("/api/geo/reverse", params={"lat": 48.85, "lon": 2.35})
    assert r.status_code == 400


def test_geo_search_and_nearby():
    r = client.get("/api/geo/search", params={"q": "Pune"})
    assert r.status_code == 200
    assert r.json()["results"][0]["district"] == "Pune"
    loc = search("Kolkata")[0]
    n = client.get("/api/geo/nearby", params={"lat": loc.lat, "lon": loc.lon, "limit": 3})
    assert n.status_code == 200
    assert len(n.json()["results"]) == 3


def test_states_and_districts():
    s = client.get("/api/states")
    assert s.status_code == 200
    assert "West Bengal" in s.json()["states"]
    d = client.get("/api/districts", params={"state": "West Bengal"})
    assert d.status_code == 200
    assert d.json()["count"] >= 20


def test_map_layers():
    r = client.get("/api/map/layers")
    assert r.status_code == 200
    ids = {b["id"] for b in r.json()["basemaps"]}
    assert {"positron", "streets", "satellite", "terrain"} <= ids
    overlays = {o["id"]: o for o in r.json()["overlays"]}
    assert overlays["bhuvan_geomorph"]["path"] == "/api/map/wms"
    assert overlays["bhuvan_geomorph"]["url"].endswith("/api/map/wms")
    assert "WB_LGEOM" in overlays["bhuvan_geomorph"]["layers"]


def test_standalone_service_card_and_openapi():
    root = client.get("/")
    assert root.status_code == 200
    body = root.json()
    assert body["service"] == "rituchakra-api"
    assert body["docs"] == "/docs"
    assert body["openapi"] == "/openapi.json"
    assert body["surfaces"]["local"]["prefix"] == "/api"
    assert body["surfaces"]["app"]["prefix"] == "/app/v1"
    catalog = client.get("/api")
    assert catalog.status_code == 200
    paths = {row["path"] for row in catalog.json()["routes"]}
    assert "/api/health" in paths
    assert "/api/dashboard" in paths
    assert "/api/chat" in paths
    assert "/api/nowcast/live" in paths
    assert "/api/nowcast/sat" in paths
    spec = client.get("/openapi.json")
    assert spec.status_code == 200
    assert spec.json()["info"]["title"] == "Rituchakra API"
    assert "/api/nowcast/live" in spec.json()["paths"]
    assert "/api/nowcast/sat" in spec.json()["paths"]


def test_cors_allows_web_origin():
    r = client.get("/api/health", headers={"Origin": "http://localhost:3000"})
    assert r.status_code == 200
    assert r.headers.get("access-control-allow-origin") == "http://localhost:3000"
    assert r.headers.get("x-api-version")
    pre = client.options(
        "/api/health",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert pre.status_code in {200, 204}
    assert pre.headers.get("access-control-allow-origin")
    expo = client.get("/api/health", headers={"Origin": "http://localhost:8081"})
    assert expo.status_code == 200
    assert expo.headers.get("access-control-allow-origin") == "http://localhost:8081"


def test_health_head():
    r = client.head("/api/health")
    assert r.status_code == 200
    assert r.headers.get("x-api-version")


def test_bootstrap():
    r = client.get("/api/bootstrap")
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True
    assert "en" in body["locales"]
    assert "advisor" in body["tabs"]
    assert body["capabilities"]["json_chat"] is True
    assert body["default_location"]["place_name"] == "Haldia"
    catalog = client.get("/api")
    paths = {row["path"] for row in catalog.json()["routes"]}
    assert "/api/bootstrap" in paths
    assert "/api/alerts" in paths
    assert "/api/market" in paths


def test_alerts_and_market(monkeypatch):
    from types import SimpleNamespace

    from app.api import dashboard as dash
    from app.services.location_svc import resolve_location

    loc = resolve_location()

    async def fake_snap(location, locale="en"):
        return SimpleNamespace(
            location=location,
            generated_at="2026-01-01T00:00:00+05:30",
            prescriptive=SimpleNamespace(warnings=[], actions=[]),
            live=SimpleNamespace(quakes=[], tsunami=[], air={}, flood={}),
            ogd={"mandi": []},
        )

    monkeypatch.setattr(dash, "build_snapshot", fake_snap)
    a = client.get("/api/alerts")
    assert a.status_code == 200
    assert a.json()["location"]["district"] == loc.district
    assert "warnings" in a.json()
    m = client.get("/api/market")
    assert m.status_code == 200
    assert "ogd" in m.json()


def test_chat_json_mode(monkeypatch):
    from app.api import chat as chat_mod

    async def fake_run(payload):
        yield {"type": "token", "text": "hold"}
        yield {"type": "final", "message": {"id": "m1", "role": "assistant", "content": "hold pump"}}

    monkeypatch.setattr(chat_mod, "run_agent", fake_run)
    r = client.post("/api/chat", json={"message": "irrigate?", "stream": False})
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True
    assert body["stream"] is False
    assert body["message"]["content"] == "hold pump"
    sse = client.post(
        "/api/chat",
        json={"message": "irrigate?"},
        headers={"Accept": "text/event-stream"},
    )
    assert sse.status_code == 200
    assert "text/event-stream" in sse.headers.get("content-type", "")

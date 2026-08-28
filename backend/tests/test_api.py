from fastapi.testclient import TestClient

from app.main import app
from app.services.location_svc import search

client = TestClient(app)


def test_health():
    r = client.get("/api/health")
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True
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

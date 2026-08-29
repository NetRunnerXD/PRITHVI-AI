from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)

PREFIXES = ("/api", "/v1", "/web/v1", "/app/v1")


def test_same_health_on_every_surface():
    bodies = []
    for prefix in PREFIXES:
        r = client.get(f"{prefix}/health")
        assert r.status_code == 200, prefix
        body = r.json()
        assert body["ok"] is True
        assert body["default_location"]["place_name"] == "Haldia"
        assert "surfaces" in body
        assert body["surfaces"]["web"]["prefix"] == "/web/v1"
        assert body["surfaces"]["app"]["prefix"] == "/app/v1"
        bodies.append(body["default_location"])
        assert r.headers.get("x-api-version")
        assert r.headers.get("x-client-surface")
    assert all(b == bodies[0] for b in bodies)


def test_surface_header_from_path_and_override():
    web = client.get("/web/v1/health")
    assert web.headers.get("x-client-surface") == "web"
    app_r = client.get("/app/v1/ready")
    assert app_r.headers.get("x-client-surface") == "app"
    forced = client.get("/api/health", headers={"X-Rituchakra-Client": "app"})
    assert forced.headers.get("x-client-surface") == "app"


def test_local_routes_still_on_api():
    catalog = client.get("/api")
    assert catalog.status_code == 200
    paths = {row["path"] for row in catalog.json()["routes"]}
    assert "/api/health" in paths
    assert "/api/dashboard" in paths
    assert "/api/chat" in paths
    assert "/web/v1/health" in paths
    assert "/app/v1/health" in paths


def test_openapi_stays_on_api_contract():
    spec = client.get("/openapi.json")
    assert spec.status_code == 200
    paths = spec.json()["paths"]
    assert "/api/health" in paths
    assert "/api/dashboard" in paths
    assert "/app/v1/health" not in paths
    assert "/web/v1/dashboard" not in paths


def test_cors_web_and_expo_together():
    web = client.get("/web/v1/health", headers={"Origin": "http://localhost:3000"})
    assert web.status_code == 200
    assert web.headers.get("access-control-allow-origin") == "http://localhost:3000"
    expo = client.get("/app/v1/health", headers={"Origin": "http://localhost:8081"})
    assert expo.status_code == 200
    assert expo.headers.get("access-control-allow-origin") == "http://localhost:8081"


def test_head_health_on_aliases():
    for prefix in PREFIXES:
        r = client.head(f"{prefix}/health")
        assert r.status_code == 200, prefix

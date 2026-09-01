from fastapi.testclient import TestClient

from app.auth.db import reset_memory
from app.auth.security import hash_otp, normalize_phone, phone_ok
from app.main import app

client = TestClient(app)

HALDIA = {"lat": 22.0667, "lon": 88.0698, "place": "Haldia"}


def setup_function():
    reset_memory()


def test_normalize_phone():
    assert normalize_phone("9876543210") == "+919876543210"
    assert phone_ok("+919876543210")
    assert not phone_ok("+911234")


def test_register_login_me():
    r = client.post(
        "/api/auth/register",
        json={
            "phone": "9876543210",
            "password": "secret123",
            "display_name": "Test Farmer",
            "sms_opt_in": True,
            **HALDIA,
        },
    )
    assert r.status_code == 200, r.text
    token = r.json()["token"]
    user = r.json()["user"]
    assert user["phone"] == "+919876543210"
    assert user["sms_opt_in"] is True
    assert user["location"]["district"]
    dup = client.post(
        "/api/auth/register",
        json={
            "phone": "9876543210",
            "password": "secret123",
            "display_name": "Other",
            **HALDIA,
        },
    )
    assert dup.status_code == 409
    bad = client.post("/api/auth/login", json={"phone": "9876543210", "password": "wrongpass"})
    assert bad.status_code == 401
    ok = client.post("/api/auth/login", json={"phone": "9876543210", "password": "secret123"})
    assert ok.status_code == 200
    me = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200
    assert me.json()["user"]["display_name"] == "Test Farmer"


def test_register_without_gps():
    r = client.post(
        "/api/auth/register",
        json={"phone": "9876500099", "password": "secret1", "sms_opt_in": False},
    )
    assert r.status_code == 200, r.text
    assert r.json()["user"]["location"] is None
    assert r.json()["user"]["display_name"].startswith("User")


def test_register_rejects_outside_india():
    r = client.post(
        "/api/auth/register",
        json={
            "phone": "9876500001",
            "password": "secret123",
            "display_name": "Paris",
            "lat": 48.85,
            "lon": 2.35,
        },
    )
    assert r.status_code == 400


def test_profile_and_location_patch():
    r = client.post(
        "/api/auth/register",
        json={"phone": "9876500002", "password": "secret123", "display_name": "A", **HALDIA},
    )
    token = r.json()["token"]
    h = {"Authorization": f"Bearer {token}"}
    p = client.patch("/api/auth/me", json={"display_name": "Arjun", "sms_opt_in": True}, headers=h)
    assert p.status_code == 200
    assert p.json()["user"]["display_name"] == "Arjun"
    loc = client.patch(
        "/api/auth/me/location",
        json={"lat": 22.5726, "lon": 88.3639, "place": "Kolkata", "source": "manual"},
        headers=h,
    )
    assert loc.status_code == 200
    assert "Kolkata" in (loc.json()["user"]["location"]["place"] or loc.json()["user"]["location"]["district"])


def test_forgot_reset(monkeypatch):
    client.post(
        "/api/auth/register",
        json={"phone": "9876500003", "password": "secret123", "display_name": "B", **HALDIA},
    )
    captured = {}

    async def fake_send(phone, message):
        captured["phone"] = phone
        captured["message"] = message
        return {"ok": True, "dry_run": True}

    monkeypatch.setattr("app.auth.router.send_sms", fake_send)
    monkeypatch.setattr("app.auth.router.new_otp", lambda: "123456")
    f = client.post("/api/auth/forgot", json={"phone": "9876500003"})
    assert f.status_code == 200
    assert "123456" in captured.get("message", "")
    bad = client.post(
        "/api/auth/reset",
        json={"phone": "9876500003", "otp": "000000", "password": "newpass12"},
    )
    assert bad.status_code == 400
    ok = client.post(
        "/api/auth/reset",
        json={"phone": "9876500003", "otp": "123456", "password": "newpass12"},
    )
    assert ok.status_code == 200
    login = client.post("/api/auth/login", json={"phone": "9876500003", "password": "newpass12"})
    assert login.status_code == 200


def test_guest_dashboard_no_auth():
    r = client.get("/api/health")
    assert r.status_code == 200


def test_otp_hash_stable():
    assert hash_otp("123456") == hash_otp("123456")
    assert hash_otp("123456") != hash_otp("654321")

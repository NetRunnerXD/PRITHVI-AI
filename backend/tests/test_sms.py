import asyncio
from types import SimpleNamespace
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.auth.sms import _digits_in, send_sms, status
from app.auth.sms_compose import fmt_ist, template_sms
from app.main import app

client = TestClient(app)

_OFF = SimpleNamespace(
    sms_enabled=False,
    sms_dry_run=True,
    fast2sms_api_key="",
    sms_demo_to="7439972482",
)


def test_digits_strip_country():
    assert _digits_in("+91 7439972482") == "7439972482"
    assert _digits_in("7439972482") == "7439972482"


def test_sms_status_off_by_default():
    with patch("app.auth.sms.get_settings", return_value=_OFF):
        st = status()
    assert st["route"] == "q"
    assert st["enabled"] is False
    assert st["dry_run"] is True
    assert "7439972482" in st["demo_to"]


def test_send_sms_dry_run_without_force():
    with patch("app.auth.sms.get_settings", return_value=_OFF):
        out = asyncio.run(send_sms("+917439972482", "hello rain 2 mm"))
    assert out["ok"] is True
    assert out["dry_run"] is True
    assert out["phone"] == "7439972482"


def test_force_send_without_key_fails():
    with patch("app.auth.sms.get_settings", return_value=_OFF):
        out = asyncio.run(send_sms("7439972482", "demo", force=True))
    assert out["ok"] is False
    assert out.get("error") == "missing_fast2sms_key"


def test_fmt_ist_readable():
    assert fmt_ist("2026-09-15T16:30:00+05:30") == "15 Sep, 4:30 pm IST"
    assert fmt_ist("2026-09-15T09:00:00Z") == "15 Sep, 2:30 pm IST"
    assert "IST" in (fmt_ist("2026-09-16T22:00:00+05:30") or "")


def test_template_sms_direct():
    text = template_sms(
        {
            "pin": "Haldia, Purba Medinipur",
            "kind": "flood",
            "start": "15 Sep, 10:20 pm IST",
            "end": "16 Sep, 6 am IST",
            "rain_mm_h": "2.4",
            "acts": ["hold irrigation", "field closed"],
        }
    )
    assert "Flooding is expected in Haldia, Purba Medinipur from 15 Sep, 10:20 pm to 16 Sep, 6 am IST." in text
    assert "Start:" not in text
    assert "Rain 2.4 mm this hour." in text
    assert "Hold irrigation and keep off the field." in text
    assert "I only quote figures" not in text
    assert "you" not in text.lower()
    assert text.endswith(".")
    assert len(text) <= 160


def test_template_sms_always_start_end_and_fits():
    text = template_sms(
        {
            "pin": "Cherrapunji, East Khasi Hills",
            "kind": "very heavy rain",
            "start": "16 Sep, 2:30 pm IST",
            "end": "16 Sep, 8:30 pm IST",
            "rain_mm_h": "18.5",
            "aqi": "312",
            "acts": ["hold irrigation", "field closed", "no outdoor work"],
        }
    )
    assert "from 16 Sep, 2:30 pm to 8:30 pm IST" in text
    assert "Start:" not in text
    assert len(text) <= 160


def test_sms_demo_status_route():
    r = client.get("/api/sms/demo")
    assert r.status_code == 200
    body = r.json()
    assert body["provider"] == "fast2sms"
    assert body["route"] == "q"


def test_sms_demo_send_without_key_is_502():
    with patch("app.auth.sms.get_settings", return_value=_OFF):
        r = client.post("/api/sms/demo/send", json={"text": "Prithvi AI demo"})
    assert r.status_code == 502
    assert "missing_fast2sms_key" in str(r.json())

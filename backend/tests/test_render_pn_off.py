from pathlib import Path

import yaml

from app.config import ROOT, cloud_light


def test_blueprint_pins_pn_off_and_cloud_light():
    doc = yaml.safe_load((ROOT.parent / "render.yaml").read_text())
    services = {s["name"]: s for s in doc["services"]}
    assert "rituchakra-api" in services
    env = {item["key"]: item.get("value") for item in services["rituchakra-api"]["envVars"]}
    assert env["PN_ENABLED"] == "0"
    assert env["CLOUD_LIGHT"] == "1"
    assert env["MOSDAC_ALLOW_L1B"] == "false"
    assert env["LLM_FALLBACK"] == "gemini,groq"


def test_cloud_light_flags(monkeypatch):
    monkeypatch.delenv("CLOUD_LIGHT", raising=False)
    monkeypatch.delenv("RENDER", raising=False)
    assert cloud_light() is False
    monkeypatch.setenv("RENDER", "true")
    assert cloud_light() is True
    monkeypatch.setenv("CLOUD_LIGHT", "0")
    assert cloud_light() is False
    monkeypatch.setenv("CLOUD_LIGHT", "1")
    assert cloud_light() is True

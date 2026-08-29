"""MOSDAC download client. Credentials from env; no invented dataset URLs."""

from __future__ import annotations

from app.config import get_settings


class NotConfigured(RuntimeError):
    pass


def credentials_present() -> bool:
    s = get_settings()
    return bool(s.mosdac_user and s.mosdac_pass)


def status() -> dict:
    s = get_settings()
    return {
        "credentials": credentials_present(),
        "base_url": bool(s.mosdac_base_url),
        "wired": bool(s.mosdac_base_url and credentials_present()),
        "note": "HEM/INSAT ingest waits on MOSDAC_BASE_URL + dataset mapping. Credentials stay in env.",
    }

"""Slim storm/lightning packs and state crop (no Mongo)."""

from __future__ import annotations

import numpy as np

from app.store import shared_packs


def test_slim_storm_drops_heavy_arrays():
    pack = {
        "ok": True,
        "state": "India",
        "cells": [{"lat": 22.0, "lon": 88.0, "kind": "storm"}],
        "grid": np.zeros((400, 400), dtype=np.float32),
        "rgba": np.zeros((200, 200, 4), dtype=np.uint8),
        "body": b"x" * 10000,
        "_ts": 1.0,
    }
    slim = shared_packs.slim_storm(pack)
    assert slim["ok"] is True
    assert slim["cells"][0]["lat"] == 22.0
    assert "grid" not in slim
    assert "rgba" not in slim
    assert "body" not in slim
    assert "_ts" not in slim


def test_crop_pack_filters_to_state():
    pack = {
        "ok": True,
        "state": "India",
        "cells": [
            {"lat": 22.07, "lon": 88.07, "kind": "storm"},  # West Bengal
            {"lat": 19.07, "lon": 72.88, "kind": "storm"},  # Maharashtra
        ],
        "predicted": [
            {"lat": 22.5, "lon": 88.3, "kind": "storm"},
            {"lat": 28.6, "lon": 77.2, "kind": "storm"},
        ],
        "sat_lightning": {
            "ok": True,
            "cells": [
                {"lat": 22.1, "lon": 88.2, "score": 0.6},
                {"lat": 13.0, "lon": 80.2, "score": 0.5},
            ],
        },
    }
    cropped = shared_packs.crop_pack(pack, "West Bengal", past_h=6)
    assert cropped["state"] == "West Bengal"
    assert cropped["past_h"] == 6
    assert len(cropped["cells"]) == 1
    assert cropped["cells"][0]["lon"] == 88.07
    assert len(cropped["predicted"]) == 1
    assert len(cropped["sat_lightning"]["cells"]) == 1


def test_mongo_roundtrip_is_noop_under_pytest():
    # sat_mongo_ok() is False during pytest, so save/load must not raise.
    assert shared_packs.save_storm({"ok": True, "cells": []}) is False
    assert shared_packs.load_storm() is None
    assert shared_packs.save_lightning({"ok": True, "cells": []}) is False
    assert shared_packs.load_lightning() is None


class _FakeCol:
    def __init__(self, row=None):
        self.row = row

    def find_one(self, *args, **kwargs):
        return dict(self.row) if self.row else None


def test_load_storm_serves_stale_within_serve_window(monkeypatch):
    import time

    saved = time.time() - 7 * 3600
    row = {
        "_id": "india",
        "ok": True,
        "source": "ingest-pack",
        "cells": [{"lat": 22.0, "lon": 88.0}],
        "predicted": [{"lat": 22.1, "lon": 88.1}],
        "saved_at": saved,
    }
    monkeypatch.setattr(shared_packs, "_col", lambda name: _FakeCol(row))
    pack = shared_packs.load_storm()
    assert pack is not None
    assert pack["ok"] is True
    assert pack["stale"] is True
    assert pack["ingest_age_s"] >= 6 * 3600
    assert pack["cells"][0]["lat"] == 22.0
    assert "stale" in (pack.get("message") or "").lower()

    row["saved_at"] = time.time() - 49 * 3600
    assert shared_packs.load_storm() is None

    row["saved_at"] = time.time() - 60
    fresh = shared_packs.load_storm()
    assert fresh is not None
    assert fresh.get("stale") is False


def test_load_lightning_serves_stale_within_serve_window(monkeypatch):
    import time

    row = {
        "_id": shared_packs.LTG_ID,
        "ok": True,
        "cells": [{"lat": 22.0, "lon": 88.0, "score": 0.6}],
        "saved_at": time.time() - 8 * 3600,
    }
    monkeypatch.setattr(shared_packs, "_col", lambda name: _FakeCol(row))
    pack = shared_packs.load_lightning()
    assert pack is not None
    assert pack["ok"] is True
    assert pack["stale"] is True
    assert pack["cells"]

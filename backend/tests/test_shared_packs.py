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

from datetime import datetime, timezone

from app.science import cv_memory


def test_mongo_off_under_pytest():
    assert cv_memory.mongo_ok() is False


def test_slim_cell_drops_bad_rows():
    assert cv_memory._slim_cell({"kind": "storm"}) is None
    row = cv_memory._slim_cell({"lat": 22.5, "lon": 88.3, "kind": "cloud", "id": "c1"})
    assert row is not None
    assert row["kind"] == "cloud"
    assert "precip_mm" not in row

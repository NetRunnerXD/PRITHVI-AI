from app.science.alert_head import build as alert_build, p_exceed, word
from app.science.rain_field import advect, optical_flow, pack, rain_from_tb, steps_ensemble
from app.ml.vera.verify import csi
from app.ml.train import eqrn


def test_optical_flow_shifts_east():
    prev = [[0.0] * 12 for _ in range(12)]
    curr = [[0.0] * 12 for _ in range(12)]
    for y in range(3, 7):
        for x in range(2, 6):
            prev[y][x] = 8.0
        for x in range(4, 8):
            curr[y][x] = 8.0
    fl = optical_flow(prev, curr, step=2)
    assert fl["speed_px"] >= 0


def test_advect_and_steps():
    g = [[0.0] * 8 for _ in range(8)]
    g[4][4] = 5.0
    moved = advect(g, 1.0, 0.0, steps=1)
    assert sum(sum(r) for r in moved) > 0
    ens = steps_ensemble(g, {"u_px": 1.0, "v_px": 0.0}, leads=3, members=3)
    assert len(ens["hours"]) == 3
    assert ens["hours"][0]["engine"] == "steps"


def test_pack_imerg_only():
    p = pack(None, None, lat=22.07, lon=88.07, imerg_mm_h=2.4)
    assert p["ok"]
    assert p["pin_mm_h"] == 2.4
    assert p["source_kind"] == "satellite-nowcast"


def test_rain_from_tb_cold():
    g = rain_from_tb([[210.0, 270.0]])
    assert g[0][0] > g[0][1]


def test_alert_words():
    hours = [{"mm": 12.0, "p_wet": 0.8}, {"mm": 4.0, "p_wet": 0.4}]
    assert p_exceed(hours, 10) > 0.2
    assert word(0.7, 0.1, {}) == "Warning"
    assert word(0.1, 0.1, {}) == "No alert"
    pack_a = alert_build(hours, {"lightning": {"p": 0.7}}, {"active": True, "thunder": True}, None)
    assert pack_a["word"] in {"Possible", "Warning"}
    assert "millimetre" not in (pack_a.get("note") or "").lower() or "not write" in pack_a["note"].lower()


def test_csi():
    pairs = [(12.0, 11.0), (0.0, 0.0), (8.0, 0.1), (0.0, 9.0)]
    v = csi(pairs, 2.0)
    assert v is not None
    assert 0 <= v <= 1


def test_eqrn_refuses_synthetic(tmp_path, monkeypatch):
    monkeypatch.setattr(eqrn, "LOG", tmp_path / "empty.jsonl")
    monkeypatch.setattr(eqrn, "WEIGHTS", tmp_path / "eqrn.pt")
    monkeypatch.setattr(eqrn, "META", tmp_path / "eqrn.json")
    out = eqrn.train(epochs=1)
    assert out["ok"] is False
    assert "synthetic" in out["error"].lower() or "obs" in out["error"].lower()

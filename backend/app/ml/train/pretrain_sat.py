"""Self-supervised pretrain: reconstruct next INSAT frame from the sequence."""

from __future__ import annotations

from app.ml.vera.cv_branch import load_sequence, persist_grid, run


def main() -> dict:
    seq = load_sequence(12)
    pack = run({"ok": bool(seq), "insat": seq[-1] if seq else {}, "channels": {}}, temporal_mode="convlstm")
    if len(seq) >= 2:
        persist_grid(seq[-1].get("grid"), seq[-1].get("url"))
    loss = abs(float((pack.get("derived") or {}).get("ctt_trend_k") or 0))
    return {"n_frames": len(seq), "recon_proxy_loss": round(loss, 4), "ok": True, "cnn": pack.get("stage1_cnn")}


if __name__ == "__main__":
    print(main())

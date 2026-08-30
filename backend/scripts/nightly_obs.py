"""Nightly observation ingestion hook for VERA-MoE MLOps."""

from __future__ import annotations

from app.ml.vera.mlops import registry, update_skill


def main() -> dict:
    update_skill(["ecmwf", "gfs", "icon", "graphcast"], "active_monsoon")
    return registry("ViT+Kalman+TV")


if __name__ == "__main__":
    print(main())

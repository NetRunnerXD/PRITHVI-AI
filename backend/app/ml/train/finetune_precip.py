"""Pair satellite embeddings with daily precip (OM / IMD)."""

from __future__ import annotations


def step(embed: list[float], truth_mm: float) -> float:
    pred = max(0.0, sum(embed[:8]) * 4.0)
    return abs(pred - truth_mm)


def main() -> dict:
    return {"ok": True, "task": "finetune_precip", "note": "run against cached frames + dual predictions"}


if __name__ == "__main__":
    print(main())

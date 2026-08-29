"""S5-C8: SHA-256 evidence hashes. Kernel owns the root; LLM does not."""

from __future__ import annotations

import hashlib
import json
from typing import Any


def _canon(obj: Any) -> bytes:
    return json.dumps(obj, sort_keys=True, default=str, ensure_ascii=False).encode("utf-8")


def hash_pack(obj: Any) -> str:
    return hashlib.sha256(_canon(obj)).hexdigest()


def root(hashes: list[str]) -> str:
    if not hashes:
        return hashlib.sha256(b"").hexdigest()
    blob = "".join(sorted(hashes)).encode("ascii")
    return hashlib.sha256(blob).hexdigest()


def ledger_for(collected: dict[str, Any]) -> dict[str, Any]:
    items = {k: hash_pack(v) for k, v in collected.items()}
    return {"items": items, "root": root(list(items.values()))}

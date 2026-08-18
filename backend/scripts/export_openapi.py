"""Write the live OpenAPI document. Run from backend/: python scripts/export_openapi.py"""

from __future__ import annotations

import json
from pathlib import Path

from app.main import app

OUT = Path(__file__).resolve().parents[1] / "openapi.json"


def main() -> None:
    spec = app.openapi()
    OUT.write_text(json.dumps(spec, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"wrote {OUT} ({len(spec.get('paths') or {})} paths)")


if __name__ == "__main__":
    main()

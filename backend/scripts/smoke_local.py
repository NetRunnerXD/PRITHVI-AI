"""Hit standalone routes on a running API. Default http://127.0.0.1:8000"""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request

BASE = os.environ.get("RITUCHAKRA_API", "http://127.0.0.1:8000").rstrip("/")


def get(path: str) -> tuple[int, dict | str]:
    req = urllib.request.Request(BASE + path, headers={"Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            raw = r.read().decode("utf-8")
            try:
                return r.status, json.loads(raw)
            except json.JSONDecodeError:
                return r.status, raw
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", errors="replace")


def main() -> int:
    checks = ["/api/health", "/api/ready", "/api/bootstrap", "/api/states", "/api"]
    bad = 0
    for path in checks:
        code, body = get(path)
        ok = code == 200
        if not ok:
            bad += 1
        snippet = body if isinstance(body, str) else json.dumps(body)[:180]
        print(f"{'OK' if ok else 'FAIL'} {code} {path}  {snippet}")
    req = urllib.request.Request(
        BASE + "/api/chat",
        data=json.dumps({"message": "ping", "stream": False}).encode(),
        headers={"Content-Type": "application/json", "Accept": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            print(f"OK {r.status} POST /api/chat stream=false")
    except Exception as e:
        print(f"FAIL POST /api/chat  {e}")
        bad += 1
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())

"""Download PN ONNX weights for Render/local when missing.

Uses ONLY these env vars (set in Render Dashboard; never commit values):
  PN_MODEL_RELEASE_REPO   e.g. NetRunnerXD/PRITHVI-AI-Archive
  PN_MODEL_RELEASE_TAG    e.g. pn-models-v7
  PN_MODEL_DOWNLOAD_TOKEN GitHub token with contents:read on that private repo ONLY
  PN_V7_MODEL_PATH / PN_CORRECT_MODEL_PATH optional overrides

Skips quietly when token unset or files already present. Does not use the
deploy SSH/git token implicitly — token must be explicitly provided.
"""
from __future__ import annotations

import os
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODELS = ROOT / "models"
ASSETS = (
    ("pn_nowcast_v7.onnx", os.environ.get("PN_V7_MODEL_PATH")),
    ("pn_correct_v6.onnx", os.environ.get("PN_CORRECT_MODEL_PATH")),
    ("pn_net_v4.onnx", None),
    ("static_v4.npy", None),
)


def main() -> int:
    if os.environ.get("PN_ENABLED", "").strip() not in {"1", "true", "yes"}:
        print("fetch_pn_models: PN_ENABLED not set; skip")
        return 0
    token = (os.environ.get("PN_MODEL_DOWNLOAD_TOKEN") or "").strip()
    repo = (os.environ.get("PN_MODEL_RELEASE_REPO") or "NetRunnerXD/PRITHVI-AI-Archive").strip()
    tag = (os.environ.get("PN_MODEL_RELEASE_TAG") or "pn-models-v7").strip()
    MODELS.mkdir(parents=True, exist_ok=True)
    missing = []
    for name, override in ASSETS:
        dest = Path(override) if override else (MODELS / name)
        if dest.is_file() and dest.stat().st_size > 1000:
            print(f"present {dest}")
            continue
        missing.append((name, dest))
    if not missing:
        return 0
    if not token:
        print(
            "fetch_pn_models: missing models and PN_MODEL_DOWNLOAD_TOKEN unset; "
            "PN will degrade until weights are provided",
            file=sys.stderr,
        )
        return 0
    for name, dest in missing:
        url = f"https://api.github.com/repos/{repo}/releases/tags/{tag}"
        # resolve asset via API then download
        req = urllib.request.Request(
            url,
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
                "User-Agent": "prithvi-pn-fetch",
            },
        )
        import json

        with urllib.request.urlopen(req, timeout=60) as r:
            meta = json.load(r)
        asset = next((a for a in meta.get("assets") or [] if a.get("name") == name), None)
        if not asset:
            print(f"asset not in release: {name}", file=sys.stderr)
            continue
        dest.parent.mkdir(parents=True, exist_ok=True)
        dl = urllib.request.Request(
            asset["url"],
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/octet-stream",
                "User-Agent": "prithvi-pn-fetch",
            },
        )
        with urllib.request.urlopen(dl, timeout=300) as r, open(dest, "wb") as f:
            while True:
                chunk = r.read(1024 * 1024)
                if not chunk:
                    break
                f.write(chunk)
        print(f"downloaded {dest} ({dest.stat().st_size} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

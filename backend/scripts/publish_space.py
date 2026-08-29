"""Upload backend/ to a Hugging Face Docker Space.

Used by .github/workflows/deploy-api.yml. Needs HF_TOKEN.
Optional HF_SPACE (default NetRunnerXD/rituchakra-api).
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from huggingface_hub import HfApi, create_repo

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
SPACE_README = ROOT / "deploy" / "space" / "README.md"
DEFAULT_SPACE = "NetRunnerXD/rituchakra-api"


def main() -> int:
    token = os.environ.get("HF_TOKEN") or os.environ.get("HUGGING_FACE_HUB_TOKEN")
    if not token:
        print("HF_TOKEN is not set. Add it as a GitHub Actions secret.", file=sys.stderr)
        return 1
    space = os.environ.get("HF_SPACE") or DEFAULT_SPACE
    api = HfApi(token=token)
    create_repo(
        space,
        repo_type="space",
        space_sdk="docker",
        exist_ok=True,
        private=False,
        token=token,
    )
    ignore = [
        ".env",
        ".env.*",
        ".cache",
        ".cache/**",
        "**/__pycache__",
        "**/*.pyc",
        ".pytest_cache",
        "tests",
        "tests/**",
        "scripts/eval_*.py",
        "scripts/scan_lightning.py",
        "scripts/smoke_local.py",
        "scripts/export_openapi.py",
        "fly.toml",
        "openapi.json",
    ]
    api.upload_folder(
        folder_path=str(BACKEND),
        repo_id=space,
        repo_type="space",
        ignore_patterns=ignore,
        commit_message="Deploy Rituchakra API from GitHub",
    )
    if SPACE_README.is_file():
        api.upload_file(
            path_or_fileobj=str(SPACE_README),
            path_in_repo="README.md",
            repo_id=space,
            repo_type="space",
            commit_message="Space card",
        )
    print(f"uploaded {space}")
    print(f"https://huggingface.co/spaces/{space}")
    slug = space.replace("/", "-").lower()
    print(f"https://{slug}.hf.space/api/ready")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

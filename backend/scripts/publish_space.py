"""Upload backend/ to a Hugging Face Docker Space.

Used by .github/workflows/deploy-api.yml. Needs HF_TOKEN (write).
Optional HF_SPACE as owner/name. If unset, uses {whoami}/rituchakra-api.
"""

from __future__ import annotations

import os
import re
import sys
import traceback
from pathlib import Path

from huggingface_hub import HfApi, create_repo
from huggingface_hub.utils import HfHubHTTPError

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
SPACE_README = ROOT / "deploy" / "space" / "README.md"
SPACE_NAME = "rituchakra-api"


def _clean(value: str | None) -> str:
    if not value:
        return ""
    return value.strip().strip('"').strip("'")


def _parse_space(raw: str, fallback_user: str) -> str:
    raw = _clean(raw)
    if not raw:
        return f"{fallback_user}/{SPACE_NAME}"
    raw = raw.replace("https://huggingface.co/spaces/", "")
    raw = raw.replace("http://huggingface.co/spaces/", "")
    raw = raw.strip("/")
    if "/" not in raw:
        return f"{fallback_user}/{raw}"
    owner, name = raw.split("/", 1)
    return f"{owner}/{name}"


def main() -> int:
    token = _clean(
        os.environ.get("HF_TOKEN")
        or os.environ.get("HUGGING_FACE_HUB_TOKEN")
        or os.environ.get("HUGGINGFACE_TOKEN")
    )
    if not token:
        print(
            "HF_TOKEN is empty in this job. Add a Hugging Face *write* token as a "
            "GitHub *repository* secret named HF_TOKEN (Settings → Secrets and "
            "variables → Actions). Environment secrets are ignored unless the "
            "workflow sets `environment:`.",
            file=sys.stderr,
        )
        return 1
    if not re.match(r"^hf_[A-Za-z0-9]+$", token):
        print(
            "HF_TOKEN does not look like a Hugging Face token (should start with hf_). "
            f"Length={len(token)} prefix={token[:3]!r}",
            file=sys.stderr,
        )
        return 1

    api = HfApi(token=token)
    try:
        me = api.whoami(token=token)
    except Exception as exc:
        print(f"Token rejected by Hugging Face whoami: {exc}", file=sys.stderr)
        print(
            "Use a classic write token, or a fine-grained token with Repositories "
            "write + Spaces write, from https://huggingface.co/settings/tokens",
            file=sys.stderr,
        )
        return 1

    user = me.get("name") or me.get("email") or ""
    print(f"huggingface user={user!r} type={me.get('type')!r} token_ok=yes")
    space = _parse_space(os.environ.get("HF_SPACE"), user)
    print(f"target space={space}")

    try:
        create_repo(
            space,
            repo_type="space",
            space_sdk="docker",
            exist_ok=True,
            private=False,
            token=token,
        )
    except HfHubHTTPError as exc:
        print(f"create_repo failed: {exc}", file=sys.stderr)
        if getattr(exc, "response", None) is not None:
            print(exc.response.text[:800], file=sys.stderr)
        return 1

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
        "scripts",
        "scripts/**",
        "fly.toml",
        "openapi.json",
    ]
    try:
        if SPACE_README.is_file():
            api.upload_file(
                path_or_fileobj=str(SPACE_README),
                path_in_repo="README.md",
                repo_id=space,
                repo_type="space",
                commit_message="Space card",
            )
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
    except Exception as exc:
        print(f"upload failed: {exc}", file=sys.stderr)
        traceback.print_exc()
        return 1

    slug = space.replace("/", "-").lower()
    print(f"uploaded {space}")
    print(f"https://huggingface.co/spaces/{space}")
    print(f"https://{slug}.hf.space/api/ready")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""One-shot: drop every non-system DB on MONGODB_SAT_URI.

    SAT_WIPE_CONFIRM=yes python -m app.ingest.wipe
"""

from __future__ import annotations

import os


def main() -> None:
    os.environ["SAT_WIPE_CONFIRM"] = "true"
    from app.config import get_settings

    get_settings.cache_clear()
    from app.store.sat_mongo import wipe_user_databases

    print(wipe_user_databases())


if __name__ == "__main__":
    main()

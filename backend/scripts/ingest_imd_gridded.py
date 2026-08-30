"""Hit IMD Pune gridded rainfall index; store pin climatology placeholder."""

from __future__ import annotations

import asyncio

from app.providers import imd_gridded


async def main() -> None:
    print(await imd_gridded.ingest_index())


if __name__ == "__main__":
    asyncio.run(main())

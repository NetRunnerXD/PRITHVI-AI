from __future__ import annotations

import asyncio

from app.providers import gpm_imerg


async def main() -> None:
    print(await gpm_imerg.fetch_pin(22.07, 88.07))


if __name__ == "__main__":
    asyncio.run(main())

"""Write mdapi config and attempt MOSDAC product download."""

from __future__ import annotations

import asyncio

from app.providers import mosdac


async def main() -> None:
    mosdac.write_mdapi_config()
    print(await mosdac.download_product())


if __name__ == "__main__":
    asyncio.run(main())

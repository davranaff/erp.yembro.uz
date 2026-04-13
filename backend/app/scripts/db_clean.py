from __future__ import annotations

import asyncio

from app.scripts.load_fixtures import _truncate_and_load


async def _main() -> None:
    await _truncate_and_load({})
    print("Database cleaned successfully.")


def main() -> None:
    asyncio.run(_main())


if __name__ == "__main__":
    main()

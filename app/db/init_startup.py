"""Optional database initialization entrypoint for demos and containers.

Run with:
    python -m app.db.init_startup

It only creates tables when INIT_DB_ON_STARTUP=true. Production deployments
should keep that flag off and run migrations explicitly.
"""

from __future__ import annotations

import asyncio

from app.core.config import settings
from app.db import init_db


async def main() -> None:
    """Create database tables when the startup flag is enabled."""
    if settings.INIT_DB_ON_STARTUP:
        await init_db()


if __name__ == "__main__":
    asyncio.run(main())

import asyncpg
from app.core.config import settings

_pool: asyncpg.Pool | None = None


async def init_db_pool() -> None:
    global _pool
    _pool = await asyncpg.create_pool(settings.DATABASE_URL)


def get_pool() -> asyncpg.Pool:
    if _pool is None:
        raise RuntimeError("Database pool has not been initialized")
    return _pool


async def close_db_pool() -> None:
    if _pool is not None:
        await _pool.close()
import pytest_asyncio

from app.db.postgres import close_db_pool, init_db_pool


@pytest_asyncio.fixture
async def db_pool():
    await init_db_pool()
    yield
    await close_db_pool()

import json

from app.core.redis import get_redis
from app.db.postgres import get_pool


CUSTOMER_LOOKUP_KEY = "customer_lookup:all"

async def refresh_customer_cache() -> None:
    pool = get_pool()

    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT
                id,
                name
            FROM customers
            ORDER BY name
            """
        )

    customers = [
        {
            "id": row["id"],
            "name": row["name"],
        }
        for row in rows
    ]

    await get_redis().set(
        CUSTOMER_LOOKUP_KEY,
        json.dumps(customers),
    )

async def get_customer_cache() -> list[dict]:
    raw = await get_redis().get(CUSTOMER_LOOKUP_KEY)

    if raw is None:
        await refresh_customer_cache()
        raw = await get_redis().get(CUSTOMER_LOOKUP_KEY)

    return json.loads(raw)    
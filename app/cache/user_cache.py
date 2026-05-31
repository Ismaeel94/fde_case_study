import json

from app.core.redis import get_redis
from app.db.postgres import get_pool

USER_LOOKUP_KEY = "user_lookup:all"

async def refresh_user_cache() -> None:
    pool = get_pool()

    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT
                id,
                username,
                full_name
            FROM users
            ORDER BY full_name
            """
        )

    users = [
        {
            "id": row["id"],
            "username": row["username"],
            "full_name": row["full_name"],
        }
        for row in rows
    ]

    await get_redis().set(
        USER_LOOKUP_KEY,
        json.dumps(users),
        ex=3600,
    )

async def get_user_cache() -> list[dict]:
    raw = await get_redis().get(USER_LOOKUP_KEY)

    if raw is None:
        await refresh_user_cache()
        raw = await get_redis().get(USER_LOOKUP_KEY)

    return json.loads(raw)    
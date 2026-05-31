from fastapi import HTTPException

from app.db.postgres import get_pool


async def get_or_create_user_from_claims(
    sub: str
) -> dict:
    pool = get_pool()
    print(f"Getting or creating user from claims: {sub}")
    async with pool.acquire() as conn:
        user = await conn.fetchrow(
            """
            SELECT id, email, username
            FROM users
            WHERE username = $1
            """,
            sub,
        )

        if user:
            return dict(user)

        raise HTTPException(status_code=401, detail="User not found in the database")

        
import json

from app.core.redis import close_redis, get_redis, init_redis

session_store: "SessionStore | None" = None


class SessionStore:
    def __init__(self, redis):
        self.redis = redis

    async def create_session(
        self,
        session_id: str,
        data: dict,
        ttl_seconds: int = 3600,
    ) -> None:
        await self.redis.set(
            f"session:{session_id}",
            json.dumps(data),
            ex=ttl_seconds,
        )

    async def get_session(self, session_id: str) -> dict | None:
        raw = await self.redis.get(f"session:{session_id}")
        if raw is None:
            return None
        return json.loads(raw)

    async def delete_session(self, session_id: str) -> None:
        await self.redis.delete(f"session:{session_id}")


async def init_session_store() -> None:
    global session_store

    await init_redis()
    session_store = SessionStore(get_redis())


async def close_session_store() -> None:
    global session_store

    await close_redis()
    session_store = None

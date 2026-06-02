import json

from app.core.redis import close_redis, get_redis, init_redis

session_store: "SessionStore | None" = None


class SessionStore:
    def __init__(self, redis):
        self.redis = redis

    def _key(self, session_id: str) -> str:
        return f"session:{session_id}"

    async def create_session(
        self,
        session_id: str,
        data: dict,
        ttl_seconds: int = 3600,
    ) -> None:
        await self.redis.set(
            self._key(session_id),
            json.dumps(data),
            ex=ttl_seconds,
        )

    async def get_session(self, session_id: str) -> dict | None:
        raw = await self.redis.get(self._key(session_id))
        if raw is None:
            return None
        return json.loads(raw)

    async def delete_session(self, session_id: str) -> None:
        await self.redis.delete(self._key(session_id))

    async def get_session_value(
        self,
        session_id: str,
        key: str,
    ):
        session = await self.get_session(session_id)
        if session is None:
            return None

        return session.get(key)

    async def set_session_value(
        self,
        session_id: str,
        key: str,
        value,
    ) -> bool:
        session = await self.get_session(session_id)
        if session is None:
            return False

        session[key] = value

        ttl = await self.redis.ttl(self._key(session_id))

        await self.redis.set(
            self._key(session_id),
            json.dumps(session),
            ex=ttl if ttl > 0 else None,
        )

        return True


async def init_session_store() -> None:
    global session_store

    await init_redis()
    session_store = SessionStore(get_redis())


async def close_session_store() -> None:
    global session_store

    await close_redis()
    session_store = None

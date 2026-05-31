from redis.asyncio import Redis

from app.core.config import settings

_redis: Redis | None = None


async def init_redis() -> None:
    global _redis
    _redis = Redis.from_url(settings.REDIS_URL)
    await _redis.ping()


def get_redis() -> Redis:
    if _redis is None:
        raise RuntimeError("Redis has not been initialized")
    return _redis


async def close_redis() -> None:
    global _redis
    if _redis is not None:
        await _redis.aclose()
    _redis = None

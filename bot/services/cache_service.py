"""Redis cache for Claude API responses.
Saves ~30% API costs by caching identical card+question combinations for 24h.
"""
import hashlib
import json
import logging
from redis.asyncio import Redis
from bot.config import settings

logger = logging.getLogger(__name__)

_redis: Redis | None = None


def get_redis() -> Redis:
    global _redis
    if _redis is None:
        _redis = Redis.from_url(settings.REDIS_URL, decode_responses=True)
    return _redis


def make_cache_key(*args) -> str:
    raw = json.dumps(args, ensure_ascii=False, sort_keys=True)
    return hashlib.md5(raw.encode()).hexdigest()


async def get_cached(key: str) -> str | None:
    try:
        return await get_redis().get(f"claude:{key}")
    except Exception as e:
        logger.warning(f"Redis get failed: {e}")
        return None


async def set_cached(key: str, value: str, ttl: int = 86400) -> None:
    try:
        await get_redis().setex(f"claude:{key}", ttl, value)
    except Exception as e:
        logger.warning(f"Redis set failed: {e}")


async def set_user_flag(user_id: int, flag: str, ttl: int = 30) -> bool:
    """Set a per-user flag with TTL. Returns False if already set (flag exists)."""
    try:
        result = await get_redis().set(f"flag:{flag}:{user_id}", 1, ex=ttl, nx=True)
        return result is not None
    except Exception:
        return True  # On Redis failure, allow the action


async def clear_user_flag(user_id: int, flag: str) -> None:
    try:
        await get_redis().delete(f"flag:{flag}:{user_id}")
    except Exception:
        pass


async def get_daily_count(user_id: int, name: str, day: str) -> int:
    """Current value of a per-user daily counter. 0 on Redis failure (fail-open)."""
    try:
        value = await get_redis().get(f"cnt:{name}:{user_id}:{day}")
        return int(value) if value else 0
    except Exception:
        return 0


async def incr_daily_count(user_id: int, name: str, day: str, ttl: int = 86400 * 2) -> None:
    try:
        redis = get_redis()
        key = f"cnt:{name}:{user_id}:{day}"
        value = await redis.incr(key)
        if value == 1:
            await redis.expire(key, ttl)
    except Exception as e:
        logger.warning(f"Redis incr failed: {e}")

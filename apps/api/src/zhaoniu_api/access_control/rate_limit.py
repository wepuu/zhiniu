from hashlib import sha256

from redis.asyncio import Redis
from redis.exceptions import RedisError

from zhaoniu_api.config import Settings


class AccessRateLimitExceeded(ValueError):
    pass


async def enforce_access_rate_limit(
    settings: Settings,
    *,
    scope: str,
    identity: str,
    limit: int = 10,
    window_seconds: int = 900,
) -> None:
    digest = sha256(identity.encode("utf-8")).hexdigest()
    key = f"zhaoniu:access-rate:{scope}:{digest}"
    client = Redis.from_url(settings.redis_url, decode_responses=True)
    try:
        count = await client.incr(key)
        if count == 1:
            await client.expire(key, window_seconds)
        if count > limit:
            raise AccessRateLimitExceeded("access_rate_limit_reached")
    except RedisError:
        if settings.app_env == "production":
            raise
    finally:
        await client.aclose()

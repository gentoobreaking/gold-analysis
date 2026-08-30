"""
Redis client wrapper for caching and session storage
"""
import json
from typing import Any

from .config import get_redis_client, init_redis  # noqa: F401


async def set_json(key: str, value: Any, ttl: int | None = None) -> None:
    """Store JSON-serializable value in Redis"""
    client = get_redis_client()
    data = json.dumps(value)
    if ttl:
        await client.set(key, data, ex=ttl)
    else:
        await client.set(key, data)


async def get_json(key: str) -> Any | None:
    """Retrieve JSON value from Redis"""
    client = get_redis_client()
    data = await client.get(key)
    if data is None:
        return None
    return json.loads(data)


async def incr(key: str, amount: int = 1, ttl: int | None = None) -> int:
    """Increment integer value with optional TTL"""
    client = get_redis_client()
    new_val = await client.incrby(key, amount)
    if ttl:
        await client.expire(key, ttl)
    return new_val


# Example cache keys
USER_SESSION_PREFIX = "session:user:"  # hash of session data per user
MARKET_PRICE_PREFIX = "cache:price:"  # latest price per asset
ALERTS_PREFIX = "cache:alerts:"  # user alerts list

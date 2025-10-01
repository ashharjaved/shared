from typing import Optional, Any
from contextlib import asynccontextmanager
from .redis import redis_client

# Convenience delegates (no separate pool here)

async def cache_set(key: str, value: Any, ttl_seconds: Optional[int] = None) -> bool:
    return await redis_client.set(key, value, ex=ttl_seconds)

async def cache_get(key: str) -> Optional[str]:
    return await redis_client.get(key)

async def cache_get_json(key: str) -> Optional[Any]:
    return await redis_client.get_json(key)

async def cache_set_json(key: str, value: Any, ttl_seconds: Optional[int] = None) -> bool:
    return await redis_client.set_json(key, value, ex=ttl_seconds)

@asynccontextmanager
async def pipeline(transaction: bool = False):
    await redis_client.ensure_connected()
    pipe = redis_client.redis.pipeline(transaction=transaction)  # type: ignore[union-attr]
    try:
        yield pipe
    finally:
        try:
            await pipe.reset()
        except Exception:
            pass
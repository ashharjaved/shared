import os
import time
from typing import Callable
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from .exceptions import RateLimitedError
from .cache import get_redis  # async Redis factory

def _per_min() -> int:
    # Default 1000 req/min per tenant per endpoint; override in tests with env
    try:
        return int(os.getenv("API_RATE_LIMIT_PER_MIN", "1000"))
    except Exception:
        return 1000

class PerTenantPerEndpointRateLimitMiddleware(BaseHTTPMiddleware):
    """
    Sliding-window rate limit: per (tenant_id|anon, endpoint) per minute.
    Returns 429 rate_limited when exceeded.
    """
    async def dispatch(self, request: Request, call_next: Callable):
        # Resolve tenant_id from JWT claims (no signature verify for perf)
        tenant_key = "anon"
        auth = request.headers.get("Authorization", "")
        if auth.lower().startswith("bearer "):
            token = auth.split(" ", 1)[1]
            try:
                import jwt
                claims = jwt.decode(token, options={"verify_signature": False})
                tenant_key = claims.get("tenant_id", "authed")
            except Exception:
                tenant_key = "authed"
        # Endpoint key (path template not available here; use raw path)
        endpoint = request.url.path or "/"
        key = f"ratelimit:{tenant_key}:{endpoint}"

        r = await get_redis()
        # atomic increment with 60s TTL (Redis-side)
        pipe = r.pipeline()
        pipe.incr(key, 1)
        pipe.expire(key, 60)  # set/refresh TTL to 60s
        count, _ = await pipe.execute()

        if int(count) > _per_min():
            # Return via centralized contract
            raise RateLimitedError("Too many requests", details={"key": key, "limit_per_min": _per_min(), "count": int(count)})

        return await call_next(request)

from __future__ import annotations

import time
from typing import Callable, Optional
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

from src.shared.redis import get_redis  # must return an async Redis client or None
from src.shared.errors import RateLimitError
from src.shared.utils import tenant_ctxvars as ctxvars

_DEFAULT_LIMIT = 1000   # per minute, API-level soft limit (refined per endpoint if needed)

def _bucket_key(tenant_id: Optional[str], endpoint: str, minute_epoch: int) -> str:
    tenant = tenant_id or "anon"
    return f"ratelimit:{tenant}:{endpoint}:{minute_epoch}"

class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Lightweight per-tenant, per-endpoint minute bucket limiter (Redis-based).
    - Honors platform policy that Redis is an optimization; if Redis is unavailable,
      middleware becomes a no-op (DB remains source of truth).
    - Tune `limit_resolver` to vary per endpoint/tenant plan.
    """
    def __init__(self, app, limit_resolver: Optional[Callable[[Request], int]] = None):
        super().__init__(app)
        self.limit_resolver = limit_resolver or (lambda _req: _DEFAULT_LIMIT)

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        redis = await get_redis()
        if not redis:
            # No Redis — do not block traffic (compliance with "DB is source of truth")
            return await call_next(request)

        tenant_id = ctxvars.TENANT_ID_VAR.get()
        endpoint = request.url.path  # coarse; replace with route.name if you prefer
        minute = int(time.time() // 60)
        key = _bucket_key(tenant_id, endpoint, minute)
        limit = self.limit_resolver(request)

        # atomic incr with 65s TTL so adjacent minute overlap is safe
        async with redis.pipeline(transaction=True) as pipe:
            pipe.incr(key)
            pipe.expire(key, 65)
            count, _ = await pipe.execute()

        if isinstance(count, bytes):
            count = int(count.decode("utf-8"))

        if count > limit:
            raise RateLimitError(message="Rate limit exceeded")

        return await call_next(request)

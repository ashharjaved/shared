from __future__ import annotations

import time
from typing import Callable, Optional
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response
from structlog import get_logger

from src.shared_.cache.redis import get_redis
from src.shared_.errors import RateLimitError
from src.shared_.utils import tenant_ctxvars as ctxvars

_DEFAULT_LIMIT = 1000  # requests per minute

def _bucket_key(tenant_id: Optional[str], endpoint: str, minute_epoch: int) -> str:
    """Generate Redis key for rate limiting."""
    tenant = tenant_id or "anon"
    return f"ratelimit:{tenant}:{endpoint}:{minute_epoch}"

class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Lightweight per-tenant, per-endpoint minute bucket limiter (Redis-based).
    """
    
    def __init__(self, app, limit_resolver: Optional[Callable[[Request], int]] = None):
        super().__init__(app)
        self.limit_resolver = limit_resolver or (lambda _req: _DEFAULT_LIMIT)

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        redis = await get_redis()
        if not redis:
            # No Redis - do not block traffic
            return await call_next(request)

        tenant_id = ctxvars.TENANT_ID_VAR.get()
        endpoint = request.url.path
        minute = int(time.time() // 60)
        key = _bucket_key(tenant_id, endpoint, minute)
        limit = self.limit_resolver(request)

        try:
            # Use Redis pipeline for atomic operations
            async with redis.pipeline(transaction=True) as pipe:
                pipe.incr(key)
                pipe.expire(key, 65)  # 65s TTL to handle minute boundaries
                results = await pipe.execute()
            
            count = results[0]
            if count > limit:
                raise RateLimitError(message="Rate limit exceeded")
                
        except Exception as e:
            # If Redis fails, allow the request but log the error
            logger = get_logger("rate_limit")
            logger.error("rate_limit_error", error=str(e))
            return await call_next(request)

        return await call_next(request)
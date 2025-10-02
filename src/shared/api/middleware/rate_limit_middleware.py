"""
Rate Limiting Middleware
Redis-based token bucket rate limiting
"""
from __future__ import annotations

import time
from typing import Any

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import JSONResponse, Response

from shared.infrastructure.cache.redis_cache import RedisCache
from shared.infrastructure.observability.logger import get_logger

logger = get_logger(__name__)


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Token bucket rate limiting middleware using Redis.
    
    Implements per-IP or per-user rate limiting to prevent abuse.
    Uses Redis for distributed rate limiting across multiple instances.
    
    Attributes:
        cache: Redis cache instance
        rate_limit: Max requests per window
        window_seconds: Time window in seconds
        enabled: Whether rate limiting is enabled
    """
    
    def __init__(
        self,
        app: Any,
        cache: RedisCache,
        rate_limit: int = 100,
        window_seconds: int = 60,
        enabled: bool = True,
    ) -> None:
        """
        Initialize rate limit middleware.
        
        Args:
            app: FastAPI application
            cache: Redis cache for storing rate limit counters
            rate_limit: Maximum requests per window (default: 100)
            window_seconds: Time window in seconds (default: 60)
            enabled: Whether to enable rate limiting (default: True)
        """
        super().__init__(app)
        self.cache = cache
        self.rate_limit = rate_limit
        self.window_seconds = window_seconds
        self.enabled = enabled
    
    async def dispatch(
        self,
        request: Request,
        call_next: RequestResponseEndpoint,
    ) -> Response:
        """
        Check rate limit before processing request.
        
        Args:
            request: Incoming FastAPI request
            call_next: Next middleware/endpoint in chain
            
        Returns:
            Response from endpoint or 429 Too Many Requests
        """
        if not self.enabled:
            return await call_next(request)
        
        # Get identifier (user_id if authenticated, else IP)
        identifier = self._get_identifier(request)
        
        # Check rate limit
        is_allowed, remaining, reset_time = await self._check_rate_limit(identifier)
        
        if not is_allowed:
            logger.warning(
                "Rate limit exceeded",
                extra={
                    "identifier": identifier,
                    "path": request.url.path,
                },
            )
            
            return JSONResponse(
                status_code=429,
                content={
                    "success": False,
                    "error": {
                        "code": "RATE_LIMIT_EXCEEDED",
                        "message": "Too many requests. Please try again later.",
                        "details": {
                            "retry_after": reset_time,
                        },
                    },
                },
                headers={
                    "X-RateLimit-Limit": str(self.rate_limit),
                    "X-RateLimit-Remaining": "0",
                    "X-RateLimit-Reset": str(reset_time),
                    "Retry-After": str(reset_time),
                },
            )
        
        # Process request
        response = await call_next(request)
        
        # Add rate limit headers
        response.headers["X-RateLimit-Limit"] = str(self.rate_limit)
        response.headers["X-RateLimit-Remaining"] = str(remaining)
        response.headers["X-RateLimit-Reset"] = str(reset_time)
        
        return response
    
    def _get_identifier(self, request: Request) -> str:
        """
        Get identifier for rate limiting (user_id or IP).
        
        Args:
            request: FastAPI request
            
        Returns:
            Identifier string
        """
        # Prefer user_id if authenticated
        if hasattr(request.state, "user_id"):
            return f"user:{request.state.user_id}"
        
        # Fall back to IP address
        client_ip = request.client.host if request.client else "unknown"
        return f"ip:{client_ip}"
    
    async def _check_rate_limit(self, identifier: str) -> tuple[bool, int, int]:
        """
        Check if request is within rate limit using token bucket algorithm.
        
        Args:
            identifier: Rate limit identifier
            
        Returns:
            Tuple of (is_allowed, remaining_requests, reset_timestamp)
        """
        key = f"rate_limit:{identifier}"
        current_time = int(time.time())
        window_start = current_time - self.window_seconds
        
        try:
            # Get current count from Redis
            count_str = await self.cache.get(key)
            
            if count_str is None:
                # First request in window
                await self.cache.set(key, 1, ttl=self.window_seconds)
                return True, self.rate_limit - 1, current_time + self.window_seconds
            
            count = int(count_str)
            
            if count >= self.rate_limit:
                # Rate limit exceeded
                ttl_key = f"{key}:ttl"
                reset_time_str = await self.cache.get(ttl_key)
                reset_time = int(reset_time_str) if reset_time_str else current_time + self.window_seconds
                return False, 0, reset_time
            
            # Increment counter
            new_count = await self.cache.increment(key)
            remaining = max(0, self.rate_limit - new_count)
            
            # Store reset time if not exists
            ttl_key = f"{key}:ttl"
            if not await self.cache.exists(ttl_key):
                reset_time = current_time + self.window_seconds
                await self.cache.set(ttl_key, reset_time, ttl=self.window_seconds)
            else:
                reset_time_str = await self.cache.get(ttl_key)
                reset_time = int(reset_time_str) if reset_time_str else current_time + self.window_seconds
            
            return True, remaining, reset_time
        except Exception as e:
            logger.error(
                "Rate limit check failed",
                extra={"error": str(e), "identifier": identifier},
            )
            # Fail open on error (allow request)
            return True, self.rate_limit, current_time + self.window_seconds
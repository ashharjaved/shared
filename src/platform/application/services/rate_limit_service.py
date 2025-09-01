from __future__ import annotations

import datetime as dt
import json
from typing import Optional, Tuple
from uuid import UUID

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.shared.exceptions import DomainError
from src.platform.domain.entities.rate_limit_policy import RateLimitScope
from src.platform.domain.repositories.rate_limit_repository import RateLimitRepository
from src.platform.infrastructure.repositories.rate_limit_repository_impl import RateLimitRepositoryImpl
from src.platform.infrastructure.cache.redis_client import RedisClient
from src.platform.application.dtos import EffectiveRateLimitDTO, RateLimitDecisionDTO
try:
    from redis.asyncio import Redis  # type: ignore
except Exception:  # pragma: no cover
    Redis = object  # fallback for typing only

class RateLimitedError(DomainError):
    code = "rate_limited"
    status_code = 429


class RateLimitService:
    """
    Sliding-window counters in Redis:
      - rl:tenant:{tenant_id}:{epoch_second}
      - rl:global:{epoch_second}
      - mon:{tenant_id}:{YYYYMM}
    """

    def __init__(self, session: AsyncSession, redis: RedisClient) -> None:
        self._session = session
        self._repo: RateLimitRepository = RateLimitRepositoryImpl(session)
        self._redis = redis

    # ---------- policy ----------

    async def effective_policy(self, tenant_id: UUID) -> Optional[EffectiveRateLimitDTO]:
        # Prefer tenant policy; fall back to global
        ten = await self._repo.get_for_tenant(tenant_id)
        if ten and not ten.is_soft_deleted():
            return EffectiveRateLimitDTO(
                requests_per_minute=ten.requests_per_minute,
                burst_limit=ten.burst_limit,
                scope=ten.scope.value,
                source="tenant",
            )

        glb = await self._repo.get_global()
        if glb and not glb.is_soft_deleted():
            return EffectiveRateLimitDTO(
                requests_per_minute=glb.requests_per_minute,
                burst_limit=glb.burst_limit,
                scope=glb.scope.value,
                source="global",
            )
        return None

    # ---------- enforcement ----------

    async def check_and_consume(
        self,
        tenant_id: UUID,
        endpoint: str,
        *,
        per_second: int,
        enable_global: bool = True,
        enable_monthly: bool = False,
        monthly_quota: Optional[int] = None,
    ) -> RateLimitDecisionDTO:
        """
        Simple per-second window using INCR + EXPIRE.
        Optional global cap and monthly meter (mon:{tenant}:{YYYYMM}).
        """
        await self._redis.connect()

        now = dt.datetime.utcnow()
        window_key_tenant = f"rl:tenant:{tenant_id}:{int(now.timestamp())}"
        ttl = 1  # second

        # tenant window
        count = await self._redis.incr_with_expire(window_key_tenant, ttl_seconds=ttl)
        if count > per_second:
            raise RateLimitedError("Too many requests for tenant window")

        # global window
        if enable_global:
            global_key = f"rl:global:{int(now.timestamp())}"
            gcount = await self._redis.incr_with_expire(global_key, ttl_seconds=ttl)
            # no configured cap passed here; callers may supply a global cap via per_second
            # We treat global the same as tenant for simplicity, but could be higher cap
            if gcount > per_second:
                raise RateLimitedError("Too many requests (global window)")

        # monthly meter (best-effort counter)
        remaining = None
        if enable_monthly and monthly_quota:
            mon_key = f"mon:{tenant_id}:{now.strftime('%Y%m')}"
            used = await self._redis.incr_with_expire(mon_key, ttl_seconds=31 * 24 * 3600)
            remaining = max(0, monthly_quota - used)
            if remaining <= 0:
                raise RateLimitedError("Monthly quota exceeded")

        return RateLimitDecisionDTO(allowed=True, remaining_in_window=max(0, per_second - count))
    
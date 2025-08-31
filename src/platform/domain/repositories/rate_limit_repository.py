from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional
from uuid import UUID

from src.platform.domain.entities.rate_limit_policy import RateLimitPolicy, RateLimitScope


class RateLimitRepository(ABC):
    """
    RLS-aware access to rate limit policies with support for GLOBAL (tenant_id is NULL).
    """

    @abstractmethod
    async def get_for_tenant(self, tenant_id: UUID) -> Optional[RateLimitPolicy]:
        """Return effective tenant-level policy for TENANT scope (non-deleted), or None."""

    @abstractmethod
    async def get_global(self) -> Optional[RateLimitPolicy]:
        """Return GLOBAL policy (non-deleted), or None."""

    @abstractmethod
    async def upsert_tenant_policy(
        self, tenant_id: UUID, requests_per_minute: int, burst_limit: int
    ) -> RateLimitPolicy:
        """Create or update TENANT-scope policy for the tenant."""

    @abstractmethod
    async def upsert_global_policy(
        self, requests_per_minute: int, burst_limit: int
    ) -> RateLimitPolicy:
        """Create or update the GLOBAL policy."""

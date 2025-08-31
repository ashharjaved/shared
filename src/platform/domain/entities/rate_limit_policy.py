from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Optional
from uuid import UUID


class RateLimitScope(str, Enum):
    """Enumeration that mirrors the DB enum `rate_limit_scope_enum`."""
    TENANT = "TENANT"
    GLOBAL = "GLOBAL"


@dataclass(frozen=True, slots=True)
class RateLimitPolicy:
    """
    Domain entity for rate limiting policy. Mirrors `rate_limit_policies`.
    """
    id: UUID
    tenant_id: Optional[UUID]  # NULL => GLOBAL
    scope: RateLimitScope
    requests_per_minute: int
    burst_limit: int
    created_at: datetime
    updated_at: datetime
    deleted_at: Optional[datetime] = None

    def is_global(self) -> bool:
        return self.tenant_id is None

    def is_soft_deleted(self) -> bool:
        return self.deleted_at is not None

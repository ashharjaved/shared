from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID
from src.shared.security import Role


@dataclass(frozen=True)
class TenantEntity:
    id: UUID
    name: str


@dataclass(frozen=True)
class UserEntity:
    id: UUID
    tenant_id: UUID
    email: str
    role: Role
    is_active: bool
    is_verified: bool
    last_login: datetime | None

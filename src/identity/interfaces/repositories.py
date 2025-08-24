from __future__ import annotations

from typing import Protocol, Optional
from uuid import UUID
from src.identity.domain.value_objects import Role
from src.identity.infrastructure.models import Tenant, User


class TenantRepositoryPort(Protocol):
    async def get_by_name(self, name: str) -> Optional[Tenant]:
        ...

    async def create_platform_owner(self, name: str, billing_email: Optional[str]) -> Tenant:
        ...


class UserRepositoryPort(Protocol):
    async def get_by_email(self, email: str) -> Optional[User]:
        ...

    async def get_by_id(self, user_id: UUID) -> Optional[User]:
        ...

    async def create_user(self, *, tenant_id: UUID, email: str, password_hash: str, role: Role) -> User:
        ...

    async def set_failed_attempts(self, user_id: UUID, attempts: int) -> None:
        ...

    async def set_last_login(self, user_id: UUID) -> None:
        ...

    async def change_password(self, user_id: UUID, new_hash: str) -> None:
        ...

    async def ensure_user(self, *, tenant_id: UUID, email: str, password_hash: str, role: Role) -> User:
        ...

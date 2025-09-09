# src/identity/infrastructure/repositories/user_repository_impl.py

from __future__ import annotations

import logging
from typing import Optional, List, Sequence

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from identity.infrastructure.mapper.user_mapper import UserMapper
from src.identity.domain.entities.user import User
from src.identity.domain.repositories.users import UserRepository
from src.identity.domain.types import UserId, TenantId
from src.identity.domain.value_objects.email import Email
from src.identity.domain.value_objects.role import Role
from src.shared.errors import DomainError, ConflictError, NotFoundError, ValidationError

from src.identity.infrastructure.models.user_model import UserModel
from src.shared.database.base_repository import BaseRepository
from ..mapper.user_mapper import UserMapper
logger = logging.getLogger(__name__)


class UserRepositoryImpl(BaseRepository[UserModel, User, UserId], UserRepository):
    """
    User repository implementation with strict tenant isolation and RLS verification.
    """

    def __init__(self, session: AsyncSession):
        super().__init__(session, UserModel, UserMapper())

    # ---------- Query methods ----------

    async def get_by_id(self, user_id: UserId, tenant_id: TenantId) -> Optional[User]:
        try:
            stmt = (
                select(UserModel)
                .where(UserModel.id == user_id)
                .where(UserModel.tenant_id == tenant_id)
            )
            res = await self._session.execute(stmt)
            model = res.scalar_one_or_none()
            return self._mapper.to_domain(model) if model else None
        except Exception as e:
            logger.error("users.get_by_id failed", extra={"user_id": str(user_id), "tenant_id": str(tenant_id), "error": str(e)})
            raise self._map_error(e)

    async def get_by_email(self, email: Email, tenant_id: TenantId) -> Optional[User]:
        try:
            stmt = (
                select(UserModel)
                .where(UserModel.email == str(email))
                .where(UserModel.tenant_id == tenant_id)
            )
            res = await self._session.execute(stmt)
            model = res.scalar_one_or_none()
            return self._mapper.to_domain(model) if model else None
        except Exception as e:
            logger.error("users.get_by_email failed", extra={"email": str(email), "tenant_id": str(tenant_id), "error": str(e)})
            raise self._map_error(e)

    async def list_by_tenant(self, tenant_id: TenantId, limit: int = 100, offset: int = 0) -> list[User]:
        try:
            stmt = (
                select(UserModel)
                .where(UserModel.tenant_id == tenant_id)
                .limit(limit)
                .offset(offset)
            )
            res = await self._session.execute(stmt)
            models = res.scalars().all()
            return [self._mapper.to_domain(m) for m in models]
        except Exception as e:
            logger.error("users.list_by_tenant failed", extra={"tenant_id": str(tenant_id), "limit": limit, "offset": offset, "error": str(e)})
            raise self._map_error(e)

    async def list_by_role(self, tenant_id: TenantId, role: Role) -> list[User]:
        try:
            # roles is a text[]; filter users that contain the role value
            stmt = (
                select(UserModel)
                .where(UserModel.tenant_id == tenant_id)
                .where(UserModel.roles.any(role.value if isinstance(role, Role) else str(role)))
            )
            res = await self._session.execute(stmt)
            models = res.scalars().all()
            return [self._mapper.to_domain(m) for m in models]
        except Exception as e:
            logger.error("users.list_by_role failed", extra={"tenant_id": str(tenant_id), "role": getattr(role, "value", str(role)), "error": str(e)})
            raise self._map_error(e)

    async def exists_by_email(self, email: Email, tenant_id: TenantId, exclude_id: Optional[UserId] = None) -> bool:
        try:
            stmt = (
                select(func.count(UserModel.id))
                .where(UserModel.tenant_id == tenant_id)
                .where(UserModel.email == str(email))
            )
            if exclude_id:
                stmt = stmt.where(UserModel.id != exclude_id)
            res = await self._session.execute(stmt)
            return (res.scalar() or 0) > 0
        except Exception as e:
            logger.error("users.exists_by_email failed", extra={"email": str(email), "tenant_id": str(tenant_id), "exclude_id": str(exclude_id) if exclude_id else None, "error": str(e)})
            raise self._map_error(e)

    async def count_by_tenant(self, tenant_id: TenantId) -> int:
        try:
            stmt = select(func.count(UserModel.id)).where(UserModel.tenant_id == tenant_id)
            res = await self._session.execute(stmt)
            return int(res.scalar() or 0)
        except Exception as e:
            logger.error("users.count_by_tenant failed", extra={"tenant_id": str(tenant_id), "error": str(e)})
            raise self._map_error(e)

    # ---------- Mutations ----------

    async def create(self, user: User) -> User:
        """
        Uses BaseRepository.create() after converting to ORM, then back to domain.
        Handles unique email per-tenant via DB constraint (mapped to ConflictError).
        """
        try:
            # Basic validation hooks (optional)
            if not str(user.email).strip():
                raise ValidationError("Email cannot be empty")
            if not user.roles or len(user.roles) == 0:
                raise ValidationError("At least one role must be assigned")

            return await super().create(user)
        except Exception as e:
            logger.error("users.create failed", extra={"tenant_id": str(user.tenant_id), "email": str(user.email), "error": str(e)})
            raise self._map_error(e)

    async def update(self, user: User) -> User:
        try:
            return await super().update(user)
        except Exception as e:
            logger.error("users.update failed", extra={"user_id": str(user.id), "tenant_id": str(user.tenant_id), "error": str(e)})
            raise self._map_error(e)

    # ---------- Mapping helpers ----------

    
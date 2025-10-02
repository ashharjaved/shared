# src/identity/infrastructure/repositories/user_repository_impl.py
from __future__ import annotations

from datetime import datetime, timezone
from typing import List, Optional
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError

from src.shared_.database.rls import verify_rls_context
from src.identity.domain.types import TenantId, UserId
from src.shared_.errors import ConflictError, NotFoundError  # aligns with BaseRepository
from src.shared_.database.base_repository import BaseRepository
from src.identity.domain.entities.user import User
from src.identity.domain.repositories.user_repository import UserRepository
from src.identity.domain.value_objects.role import Role
from src.identity.infrastructure.models.user_model import UserModel
from src.identity.infrastructure.Mappers.user_mapper import UserMapper


class UserRepositoryImpl(BaseRepository[UserModel, User, UUID], UserRepository):
    """
    SQLAlchemy implementation of the UserRepository with RLS enforcement through BaseRepository.
    - No explicit commits here; let services/UoW manage transactions.
    - Uses ctxvars-backed TenantContext inside BaseRepository for RLS.
    """

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session=session, model_class= UserModel, mapper= UserMapper())

    # -------- Lookup methods -------------------------------------------------

    async def find_by_id(self, user_id: UserId) -> Optional[User]:
        # delegates to generic get_by_id (RLS enforced)
        return await self.get_by_id(user_id)

    async def find_by_email(self, email: str, tenant_id: TenantId) -> Optional[User]:
        # RLS is enforced; we still include tenant_id to be explicit for query selectivity
        return await self.get_one(email=email, tenant_id=tenant_id)

    # -------- Mutations / counters ------------------------------------------

    async def update_last_login(self, user_id: UserId, login_time: datetime) -> None:
        await verify_rls_context(self._session)        
        stmt = (
            update(UserModel)
            .where(UserModel.id == user_id)
            .values(last_login=login_time.astimezone(timezone.utc).replace(tzinfo=None),
                    updated_at=datetime.utcnow())
        )
        result = await self._session.execute(stmt)
        if result.rowcount == 0:
            raise NotFoundError(f"User with ID {user_id} not found or not accessible")

    async def increment_failed_logins(self, user_id: UserId) -> int:
        await verify_rls_context(self._session)
        stmt = (
            update(UserModel)
            .where(UserModel.id == user_id)
            .values(
                failed_login_attempts=UserModel.failed_login_attempts + 1,
                updated_at=datetime.utcnow(),
            )
            .returning(UserModel.failed_login_attempts)
        )
        result = await self._session.execute(stmt)
        row = result.fetchone()
        if not row:
            raise NotFoundError(f"User with ID {user_id} not found or not accessible")
        return int(row[0])

    async def reset_failed_logins(self, user_id: UserId) -> None:
        await verify_rls_context(self._session)
        stmt = (
            update(UserModel)
            .where(UserModel.id == user_id)
            .values(failed_login_attempts=0, updated_at=datetime.utcnow())
        )
        result = await self._session.execute(stmt)
        if result.rowcount == 0:
            raise NotFoundError(f"User with ID {user_id} not found or not accessible")

    # -------- Listing --------------------------------------------------------

    async def list_by_tenant(
        self,
        tenant_id: TenantId,
        role: Optional[Role] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[User]:
        stmt = select(UserModel).where(UserModel.tenant_id == tenant_id)
        if role is not None:
            stmt = stmt.where(UserModel.role == role)
        stmt = stmt.limit(limit).offset(offset)

        result = await self._session.execute(stmt)
        models = result.scalars().all()
        return [self._mapper.to_domain(m) for m in models]
    
    # -------- Creation -------------------------------------------------------
    async def create(self, user: User) -> User:
        """Create a new user (no commit)."""
        try:
            return await super().create(user)
        except IntegrityError as e:
            # Provide a more domain-specific message when unique email conflicts.
            msg = str(e).lower()
            if "uq_users_tenant_email" in msg or "unique" in msg and "email" in msg:
                raise ConflictError(f"User with email '{user.email}' already exists in tenant")
            raise

    async def update(self, user: User) -> User:
        """Update an existing user (no commit)."""
        try:
            return await super().update(user)
        except IntegrityError as e:
            msg = str(e).lower()
            if "uq_users_tenant_email" in msg or "unique" in msg and "email" in msg:
                raise ConflictError(f"User with email '{user.email}' already exists in tenant")
            raise

    async def change_role(self, user_id: UserId, new_role: Role) -> User:
        try:
            # Ensure the new role is valid
            return await super().update_fields(user_id, role=new_role)
        except IntegrityError as e:
            raise ConflictError(f"Failed to change role: {str(e)}") from e
        

    async def deactivate(self, user_id: UserId) -> User:
        try:
            return await super().update_fields(user_id, is_active=False)
        except IntegrityError as e:
            raise ConflictError(f"Failed to deactivate user: {str(e)}") from e

    async def reactivate(self, user_id: UserId) -> User:
        try:
            return await super().update_fields(user_id, is_active=True) 
        except IntegrityError as e:
            raise ConflictError(f"Failed to reactivate user: {str(e)}") from e
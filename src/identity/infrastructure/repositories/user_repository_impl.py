# src/identity/infrastructure/repositories/user_repository_impl.py

from datetime import datetime
from typing import List, Optional
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError

from src.identity.domain.entities.user import User
from src.identity.domain.repositories.user_repository import UserRepository
from shared.roles import Role
from src.identity.infrastructure.models.user_model import UserModel
from src.shared.exceptions import ConflictError, NotFoundError
from src.shared.database import set_rls_guc


class UserRepositoryImpl(UserRepository):
    """
    SQLAlchemy implementation of user repository with RLS enforcement.
    
    All operations automatically enforce tenant isolation through
    Row-Level Security policies.
    """
    
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
    
    async def find_by_email(self, email: str, tenant_id: UUID) -> Optional[User]:
        """Find user by email within a tenant."""
        # Set tenant context for RLS
        await set_rls_guc(self._session, tenant_id=str(tenant_id))
        
        stmt = select(UserModel).where(
            UserModel.email == email,
            UserModel.tenant_id == tenant_id
        )
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        return model.to_domain() if model else None
    
    async def find_by_id(self, user_id: UUID) -> Optional[User]:
        """Find user by ID (with RLS enforcement)."""
        stmt = select(UserModel).where(UserModel.id == user_id)
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        return model.to_domain() if model else None
    
    async def create(self, user: User) -> User:
        """Create a new user."""
        # Set tenant context for RLS
        await set_rls_guc(self._session, user_id=str(user.tenant_id))
        
        try:
            model = UserModel.from_domain(user)
            self._session.add(model)
            await self._session.flush()
            await self._session.refresh(model)
            return model.to_domain()
        except IntegrityError as e:
            await self._session.rollback()
            if "uq_users_tenant_email" in str(e) or "email" in str(e):
                raise ConflictError(f"User with email '{user.email}' already exists in tenant")
            raise ConflictError("Failed to create user due to constraint violation")
    
    async def update(self, user: User) -> User:
        """Update an existing user."""
        # Set tenant context for RLS
        await set_rls_guc(self._session, tenant_id=str(user.tenant_id))
        
        stmt = select(UserModel).where(UserModel.id == user.id)
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        
        if not model:
            raise NotFoundError(f"User with ID {user.id} not found or not accessible")
        
        try:
            # Update fields
            model.email = user.email
            model.password_hash = user.password_hash
            model.role = user.role
            model.is_active = user.is_active
            model.is_verified = user.is_verified
            model.failed_login_attempts = user.failed_login_attempts
            model.last_login = user.last_login
            model.updated_at = user.updated_at
            
            await self._session.flush()
            await self._session.refresh(model)
            return model.to_domain()
        except IntegrityError as e:
            await self._session.rollback()
            if "uq_users_tenant_email" in str(e) or "email" in str(e):
                raise ConflictError(f"User with email '{user.email}' already exists in tenant")
            raise ConflictError("Failed to update user due to constraint violation")
    
    async def update_last_login(self, user_id: UUID, login_time: datetime) -> None:
        """Update user's last login timestamp."""
        stmt = (
            update(UserModel)
            .where(UserModel.id == user_id)
            .values(last_login=login_time, updated_at=datetime.utcnow())
        )
        result = await self._session.execute(stmt)
        
        if result.rowcount == 0:
            raise NotFoundError(f"User with ID {user_id} not found or not accessible")
    
    async def increment_failed_logins(self, user_id: UUID) -> int:
        """Increment failed login attempts counter."""
        stmt = (
            update(UserModel)
            .where(UserModel.id == user_id)
            .values(
                failed_login_attempts=UserModel.failed_login_attempts + 1,
                updated_at=datetime.utcnow()
            )
            .returning(UserModel.failed_login_attempts)
        )
        result = await self._session.execute(stmt)
        row = result.fetchone()
        
        if not row:
            raise NotFoundError(f"User with ID {user_id} not found or not accessible")
        
        return row[0]
    
    async def reset_failed_logins(self, user_id: UUID) -> None:
        """Reset failed login attempts counter to zero."""
        stmt = (
            update(UserModel)
            .where(UserModel.id == user_id)
            .values(failed_login_attempts=0, updated_at=datetime.utcnow())
        )
        result = await self._session.execute(stmt)
        
        if result.rowcount == 0:
            raise NotFoundError(f"User with ID {user_id} not found or not accessible")
    
    async def list_by_tenant(
        self,
        tenant_id: UUID,
        role: Optional[Role] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[User]:
        """List users in a tenant with optional role filtering."""
        # Set tenant context for RLS
        await set_rls_guc(self._session, tenant_id=str(tenant_id))
        
        stmt = select(UserModel).where(UserModel.tenant_id == tenant_id)
        
        if role:
            stmt = stmt.where(UserModel.role == role)
        
        stmt = stmt.limit(limit).offset(offset)
        
        result = await self._session.execute(stmt)
        models = result.scalars().all()
        return [model.to_domain() for model in models]
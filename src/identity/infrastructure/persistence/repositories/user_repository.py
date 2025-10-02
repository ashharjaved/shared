"""
User Repository Implementation
"""
from __future__ import annotations

from typing import Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from shared.infrastructure.database.sqlalchemy_repository import SQLAlchemyRepository
from src.identity.domain.entities.user import User
from src.identity.domain.value_objects.email import Email
from src.identity.domain.value_objects.phone import Phone
from src.identity.domain.value_objects.password_hash import PasswordHash
from src.identity.infrastructure.persistence.models.user_model import UserModel


class UserRepository(SQLAlchemyRepository[User, UserModel]):
    """
    User repository implementation.
    
    RLS-aware: Queries automatically scoped by organization_id.
    Tracks aggregates for domain event collection.
    """
    
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(
            session=session,
            model_class=UserModel,
            entity_class=User,
        )
        self._uow = None  # Will be set by UoW if needed
    
    def set_uow(self, uow) -> None:
        """Set Unit of Work for aggregate tracking"""
        self._uow = uow
    
    def _to_entity(self, model: UserModel) -> User:
        """Convert ORM model to domain entity"""
        return User(
            id=model.id,
            organization_id=model.organization_id,
            email=Email(model.email),
            password_hash=PasswordHash(model.password_hash),
            full_name=str(model.full_name),
            phone=Phone(model.phone) if model.phone else None,
            is_active=model.is_active,
            email_verified=model.email_verified,
            phone_verified=model.phone_verified,
            last_login_at=model.last_login_at,
            failed_login_attempts=model.failed_login_attempts,
            locked_until=model.locked_until,
            metadata=model.metadata,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )
    
    def _to_model(self, entity: User) -> UserModel:
        """Convert domain entity to ORM model"""
        return UserModel(
            id=entity.id,
            organization_id=entity.organization_id,
            email=str(entity.email),
            phone=str(entity.phone) if entity.phone else None,
            password_hash=entity.password_hash.value,
            full_name=entity.full_name,
            is_active=entity.is_active,
            email_verified=entity.email_verified,
            phone_verified=entity.phone_verified,
            last_login_at=entity.last_login_at,
            failed_login_attempts=entity._failed_login_attempts,
            locked_until=entity._locked_until,
            metadata=entity.metadata,
            created_at=entity.created_at,
            updated_at=entity.updated_at,
        )
    
    async def add(self, entity: User) -> User:
        """Add new user and track for events"""
        result = await super().add(entity)
        
        # Track aggregate for domain event collection
        if self._uow:
            self._uow.track_aggregate(entity)
        
        return result
    
    async def update(self, entity: User) -> User:
        """Update user and track for events"""
        result = await super().update(entity)
        
        # Track aggregate for domain event collection
        if self._uow:
            self._uow.track_aggregate(entity)
        
        return result
    
    async def get_by_email(self, email: Email) -> Optional[User]:
        """
        Get user by email address.
        
        Args:
            email: Email value object
            
        Returns:
            User if found, None otherwise
        """
        stmt = select(UserModel).where(
            UserModel.email == str(email),
            UserModel.deleted_at.is_(None),
        )
        
        result = await self.session.execute(stmt)
        model = result.scalar_one_or_none()
        
        return self._to_entity(model) if model else None
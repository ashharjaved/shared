"""
ApiKey Repository Implementation
"""
from __future__ import annotations

from typing import Optional, Sequence
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from shared.infrastructure.database.sqlalchemy_repository import SQLAlchemyRepository
from src.identity.domain.entities.api_key import ApiKey
from src.identity.domain.value_objects.permission import Permission
from src.identity.infrastructure.persistence.models.api_key_model import (
    ApiKeyModel,
)


class ApiKeyRepository(SQLAlchemyRepository[ApiKey, ApiKeyModel]):
    """
    ApiKey repository implementation.
    
    Handles API key persistence with hashed storage.
    """
    
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(
            session=session,
            model_class=ApiKeyModel,
            entity_class=ApiKey,
        )
    
    def _to_entity(self, model: ApiKeyModel) -> ApiKey:
        """Convert ORM model to domain entity"""
        permissions = {Permission(p) for p in model.permissions}
        
        return ApiKey(
            id=model.id,
            organization_id=model.organization_id,
            user_id=model.user_id,
            name=model.name,
            key_hash=model.key_hash,
            key_prefix=model.key_prefix,
            permissions=permissions,
            last_used_at=model.last_used_at,
            expires_at=model.expires_at,
            is_active=model.is_active,
            revoked_at=model.revoked_at,
            created_at=model.created_at,
        )
    
    def _to_model(self, entity: ApiKey) -> ApiKeyModel:
        """Convert domain entity to ORM model"""
        permissions_list = [p.value for p in entity.permissions]
        
        return ApiKeyModel(
            id=entity.id,
            organization_id=entity.organization_id,
            user_id=entity.user_id,
            name=entity.name,
            key_hash=entity.key_hash,
            key_prefix=entity.key_prefix,
            permissions=permissions_list,
            last_used_at=entity.last_used_at,
            expires_at=entity.expires_at,
            is_active=entity.is_active,
            revoked_at=entity.revoked_at,
            created_at=entity.created_at,
        )
    
    async def get_by_prefix(self, key_prefix: str) -> Optional[ApiKey]:
        """
        Get API key by prefix (for quick lookup).
        
        Args:
            key_prefix: Key prefix (e.g., 'sk_live_abc123')
            
        Returns:
            ApiKey if found, None otherwise
        """
        stmt = select(ApiKeyModel).where(ApiKeyModel.key_prefix == key_prefix)
        
        result = await self.session.execute(stmt)
        model = result.scalar_one_or_none()
        
        return self._to_entity(model) if model else None
    
    async def get_by_hash(self, key_hash: str) -> Optional[ApiKey]:
        """
        Get API key by hash (for verification).
        
        Args:
            key_hash: SHA-256 hash of key
            
        Returns:
            ApiKey if found, None otherwise
        """
        stmt = select(ApiKeyModel).where(ApiKeyModel.key_hash == key_hash)
        
        result = await self.session.execute(stmt)
        model = result.scalar_one_or_none()
        
        return self._to_entity(model) if model else None
    
    async def find_by_organization(
        self,
        organization_id: UUID,
        skip: int = 0,
        limit: int = 100,
        is_active: Optional[bool] = None,
    ) -> Sequence[ApiKey]:
        """
        Find all API keys for an organization.
        
        Args:
            organization_id: Organization UUID
            skip: Number of records to skip
            limit: Maximum records to return
            is_active: Filter by active status
            
        Returns:
            List of API keys
        """
        stmt = select(ApiKeyModel).where(
            ApiKeyModel.organization_id == organization_id
        )
        
        if is_active is not None:
            stmt = stmt.where(ApiKeyModel.is_active == is_active)
        
        stmt = stmt.offset(skip).limit(limit).order_by(ApiKeyModel.created_at.desc())
        
        result = await self.session.execute(stmt)
        models = result.scalars().all()
        
        return [self._to_entity(model) for model in models]
"""
RefreshToken Repository Implementation
"""
from __future__ import annotations

from typing import Optional, Sequence
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from shared.infrastructure.database.sqlalchemy_repository import SQLAlchemyRepository
from src.identity.domain.entities.refresh_token import RefreshToken
from src.identity.infrastructure.persistence.models.refresh_token_model import (
    RefreshTokenModel,
)


class RefreshTokenRepository(SQLAlchemyRepository[RefreshToken, RefreshTokenModel]):
    """
    RefreshToken repository implementation.
    
    Handles JWT refresh token persistence.
    """
    
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(
            session=session,
            model_class=RefreshTokenModel,
            entity_class=RefreshToken,
        )
    
    def _to_entity(self, model: RefreshTokenModel) -> RefreshToken:
        """Convert ORM model to domain entity"""
        return RefreshToken(
            id=model.id,
            user_id=model.user_id,
            token_hash=model.token_hash,
            expires_at=model.expires_at,
            revoked_at=model.revoked_at,
            created_at=model.created_at,
        )
    
    def _to_model(self, entity: RefreshToken) -> RefreshTokenModel:
        """Convert domain entity to ORM model"""
        return RefreshTokenModel(
            id=entity.id,
            user_id=entity.user_id,
            token_hash=entity.token_hash,
            expires_at=entity.expires_at,
            revoked_at=entity.revoked_at,
            created_at=entity.created_at,
        )
    
    async def get_by_hash(self, token_hash: str) -> Optional[RefreshToken]:
        """
        Get token by hash.
        
        Args:
            token_hash: SHA-256 hash of token
            
        Returns:
            RefreshToken if found, None otherwise
        """
        stmt = select(RefreshTokenModel).where(
            RefreshTokenModel.token_hash == token_hash
        )
        
        result = await self.session.execute(stmt)
        model = result.scalar_one_or_none()
        
        return self._to_entity(model) if model else None
    
    async def find_by_user(
        self,
        user_id: UUID,
        include_revoked: bool = False,
    ) -> Sequence[RefreshToken]:
        """
        Find all tokens for a user.
        
        Args:
            user_id: User UUID
            include_revoked: Include revoked tokens
            
        Returns:
            List of refresh tokens
        """
        stmt = select(RefreshTokenModel).where(
            RefreshTokenModel.user_id == user_id
        )
        
        if not include_revoked:
            stmt = stmt.where(RefreshTokenModel.revoked_at.is_(None))
        
        stmt = stmt.order_by(RefreshTokenModel.created_at.desc())
        
        result = await self.session.execute(stmt)
        models = result.scalars().all()
        
        return [self._to_entity(model) for model in models]
    
    async def revoke_all_for_user(self, user_id: UUID) -> None:
        """
        Revoke all tokens for a user (logout all devices).
        
        Args:
            user_id: User UUID
        """
        from datetime import datetime
        
        stmt = (
            update(RefreshTokenModel)
            .where(
                RefreshTokenModel.user_id == user_id,
                RefreshTokenModel.revoked_at.is_(None),
            )
            .values(revoked_at=datetime.utcnow())
        )
        
        await self.session.execute(stmt)
    
    async def delete_expired(self) -> int:
        """
        Delete all expired tokens (cleanup job).
        
        Returns:
            Number of tokens deleted
        """
        from datetime import datetime
        from sqlalchemy import delete
        
        stmt = delete(RefreshTokenModel).where(
            RefreshTokenModel.expires_at < datetime.utcnow()
        )
        
        result = await self.session.execute(stmt)
        return result.rowcount
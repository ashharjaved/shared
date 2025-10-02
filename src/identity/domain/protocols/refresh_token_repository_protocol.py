"""
RefreshToken Repository Protocol (Interface)
"""
from __future__ import annotations

from typing import Optional, Protocol, Sequence
from uuid import UUID

from src.identity.domain.entities.refresh_token import RefreshToken


class IRefreshTokenRepository(Protocol):
    """Refresh token repository interface"""
    
    async def add(self, token: RefreshToken) -> RefreshToken:
        """Add new refresh token"""
        ...
    
    async def get_by_id(self, token_id: UUID) -> Optional[RefreshToken]:
        """Get token by ID"""
        ...
    
    async def get_by_hash(self, token_hash: str) -> Optional[RefreshToken]:
        """Get token by hash"""
        ...
    
    async def find_by_user(
        self,
        user_id: UUID,
        include_revoked: bool = False,
    ) -> Sequence[RefreshToken]:
        """Find all tokens for a user"""
        ...
    
    async def update(self, token: RefreshToken) -> RefreshToken:
        """Update token (e.g., revoke)"""
        ...
    
    async def revoke_all_for_user(self, user_id: UUID) -> None:
        """Revoke all tokens for a user (logout all devices)"""
        ...
    
    async def delete_expired(self) -> int:
        """Delete all expired tokens (cleanup job)"""
        ...
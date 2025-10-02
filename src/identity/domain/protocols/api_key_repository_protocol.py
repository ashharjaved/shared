"""
ApiKey Repository Protocol (Interface)
"""
from __future__ import annotations

from typing import Optional, Protocol, Sequence
from uuid import UUID

from src.identity.domain.entities.api_key import ApiKey


class IApiKeyRepository(Protocol):
    """API key repository interface"""
    
    async def add(self, api_key: ApiKey) -> ApiKey:
        """Add new API key"""
        ...
    
    async def get_by_id(self, key_id: UUID) -> Optional[ApiKey]:
        """Get API key by ID"""
        ...
    
    async def get_by_prefix(self, key_prefix: str) -> Optional[ApiKey]:
        """Get API key by prefix (for quick lookup)"""
        ...
    
    async def get_by_hash(self, key_hash: str) -> Optional[ApiKey]:
        """Get API key by hash (for verification)"""
        ...
    
    async def find_by_organization(
        self,
        organization_id: UUID,
        skip: int = 0,
        limit: int = 100,
        is_active: Optional[bool] = None,
    ) -> Sequence[ApiKey]:
        """Find all API keys for an organization"""
        ...
    
    async def update(self, api_key: ApiKey) -> ApiKey:
        """Update API key (e.g., revoke, update last_used)"""
        ...
    
    async def delete(self, key_id: UUID) -> None:
        """Delete API key"""
        ...
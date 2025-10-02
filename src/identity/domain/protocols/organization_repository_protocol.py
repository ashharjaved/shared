"""
Organization Repository Protocol (Interface)
"""
from __future__ import annotations

from typing import Optional, Protocol, Sequence
from uuid import UUID

from src.identity.domain.entities.organization import Organization


class IOrganizationRepository(Protocol):
    """Organization repository interface"""
    
    async def add(self, organization: Organization) -> Organization:
        """Add new organization"""
        ...
    
    async def get_by_id(self, org_id: UUID) -> Optional[Organization]:
        """Get organization by ID"""
        ...
    
    async def get_by_slug(self, slug: str) -> Optional[Organization]:
        """Get organization by slug"""
        ...
    
    async def find_all(
        self,
        skip: int = 0,
        limit: int = 100,
        is_active: Optional[bool] = None,
    ) -> Sequence[Organization]:
        """Find all organizations with filters"""
        ...
    
    async def update(self, organization: Organization) -> Organization:
        """Update existing organization"""
        ...
    
    async def delete(self, org_id: UUID) -> None:
        """Soft delete organization"""
        ...
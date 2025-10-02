"""
Role Repository Protocol (Interface)
"""
from __future__ import annotations

from typing import Optional, Protocol, Sequence
from uuid import UUID

from src.identity.domain.entities.role import Role


class IRoleRepository(Protocol):
    """Role repository interface"""
    
    async def add(self, role: Role) -> Role:
        """Add new role"""
        ...
    
    async def get_by_id(self, role_id: UUID) -> Optional[Role]:
        """Get role by ID"""
        ...
    
    async def get_by_name(
        self,
        organization_id: UUID,
        name: str,
    ) -> Optional[Role]:
        """Get role by name within organization"""
        ...
    
    async def find_by_organization(
        self,
        organization_id: UUID,
        skip: int = 0,
        limit: int = 100,
    ) -> Sequence[Role]:
        """Find all roles for an organization"""
        ...
    
    async def find_system_roles(self) -> Sequence[Role]:
        """Find all system roles"""
        ...
    
    async def update(self, role: Role) -> Role:
        """Update existing role"""
        ...
    
    async def delete(self, role_id: UUID) -> None:
        """Soft delete role"""
        ...
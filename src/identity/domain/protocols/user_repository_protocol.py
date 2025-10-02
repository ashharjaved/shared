"""
User Repository Protocol (Interface)
"""
from __future__ import annotations

from typing import Optional, Protocol
from uuid import UUID

from src.identity.domain.entities.user import User
from src.identity.domain.value_objects.email import Email


class IUserRepository(Protocol):
    """User repository interface"""
    
    async def add(self, user: User) -> User:
        """Add new user"""
        ...
    
    async def get_by_id(self, user_id: UUID) -> Optional[User]:
        """Get user by ID"""
        ...
    
    async def get_by_email(self, email: Email) -> Optional[User]:
        """Get user by email address"""
        ...
    
    async def update(self, user: User) -> User:
        """Update existing user"""
        ...
    
    async def delete(self, user_id: UUID) -> None:
        """Soft delete user"""
        ...
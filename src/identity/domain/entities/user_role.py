"""
UserRole Entity - User-Role Assignment Mapping
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import UUID

from shared.domain.base_entity import BaseEntity


class UserRole(BaseEntity):
    """
    User-Role assignment entity.
    
    Represents the many-to-many relationship between users and roles.
    Tracks when the role was granted and by whom for audit purposes.
    
    Attributes:
        user_id: User UUID
        role_id: Role UUID
        granted_at: Timestamp when role was granted
        granted_by: User ID who granted this role (optional)
    """
    
    def __init__(
        self,
        id: UUID,
        user_id: UUID,
        role_id: UUID,
        granted_at: datetime,
        granted_by: Optional[UUID] = None,
        created_at: Optional[datetime] = None,
        updated_at: Optional[datetime] = None,
    ) -> None:
        super().__init__(id, created_at, updated_at)
        self._user_id = user_id
        self._role_id = role_id
        self._granted_at = granted_at
        self._granted_by = granted_by
    
    @staticmethod
    def create(
        id: UUID,
        user_id: UUID,
        role_id: UUID,
        granted_by: Optional[UUID] = None,
    ) -> UserRole:
        """
        Factory method to create a new user-role assignment.
        
        Args:
            id: Assignment UUID
            user_id: User UUID
            role_id: Role UUID
            granted_by: User who granted this role
            
        Returns:
            New UserRole instance
        """
        return UserRole(
            id=id,
            user_id=user_id,
            role_id=role_id,
            granted_at=datetime.utcnow(),
            granted_by=granted_by,
        )
    
    # Properties
    @property
    def user_id(self) -> UUID:
        return self._user_id
    
    @property
    def role_id(self) -> UUID:
        return self._role_id
    
    @property
    def granted_at(self) -> datetime:
        return self._granted_at
    
    @property
    def granted_by(self) -> Optional[UUID]:
        return self._granted_by
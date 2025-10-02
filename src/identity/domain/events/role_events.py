"""
Role Domain Events
"""
from __future__ import annotations

from datetime import datetime
from typing import List
from uuid import UUID

from shared.domain.domain_event import DomainEvent


class RoleCreatedEvent(DomainEvent):
    """Raised when a new role is created"""
    
    def __init__(
        self,
        role_id: UUID,
        organization_id: UUID,
        name: str,
        is_system: bool,
        permissions: List[str],
        occurred_at: datetime | None = None,
    ) -> None:
        if occurred_at is not None:
            super().__init__(occurred_at=occurred_at)
        else:
            super().__init__()
        self.role_id = role_id
        self.organization_id = organization_id
        self.name = name
        self.is_system = is_system
        self.permissions = permissions


class PermissionGrantedEvent(DomainEvent):
    """Raised when a permission is granted to a role"""
    
    def __init__(
        self,
        role_id: UUID,
        organization_id: UUID,
        role_name: str,
        permission: str,
        occurred_at: datetime | None = None,
    ) -> None:
        if occurred_at is not None:
            super().__init__(occurred_at=occurred_at)
        else:
            super().__init__()
        self.role_id = role_id
        self.organization_id = organization_id
        self.role_name = role_name
        self.permission = permission


class PermissionRevokedEvent(DomainEvent):
    """Raised when a permission is revoked from a role"""
    
    def __init__(
        self,
        role_id: UUID,
        organization_id: UUID,
        role_name: str,
        permission: str,
        occurred_at: datetime | None = None,
    ) -> None:
        if occurred_at is not None:
            super().__init__(occurred_at=occurred_at)
        else:
            super().__init__()
        self.role_id = role_id
        self.organization_id = organization_id
        self.role_name = role_name
        self.permission = permission


class RoleAssignedEvent(DomainEvent):
    """Raised when a role is assigned to a user"""
    
    def __init__(
        self,
        user_id: UUID,
        role_id: UUID,
        organization_id: UUID,
        role_name: str,
        assigned_by: UUID | None,
        occurred_at: datetime | None = None,
    ) -> None:
        if occurred_at is not None:
            super().__init__(occurred_at=occurred_at)
        else:
            super().__init__()
        self.user_id = user_id
        self.role_id = role_id
        self.organization_id = organization_id
        self.role_name = role_name
        self.assigned_by = assigned_by


class RoleRevokedEvent(DomainEvent):
    """Raised when a role is revoked from a user"""
    
    def __init__(
        self,
        user_id: UUID,
        role_id: UUID,
        organization_id: UUID,
        role_name: str,
        revoked_by: UUID | None,
        occurred_at: datetime | None = None,
    ) -> None:
        if occurred_at is not None:
            super().__init__(occurred_at=occurred_at)
        else:
            super().__init__()
        self.user_id = user_id
        self.role_id = role_id
        self.organization_id = organization_id
        self.role_name = role_name
        self.revoked_by = revoked_by
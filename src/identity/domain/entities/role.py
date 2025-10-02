"""
Role Entity - RBAC Role Management
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional, Set
from uuid import UUID

from shared.domain.base_aggregate_root import BaseAggregateRoot
from src.identity.domain.value_objects.permission import Permission
from src.identity.domain.events.role_events import (
    RoleCreatedEvent,
    PermissionGrantedEvent,
    PermissionRevokedEvent,
)
from src.identity.domain.exception import PermissionDeniedException


class Role(BaseAggregateRoot):
    """
    Role aggregate root for RBAC.
    
    Manages role definition and permission assignment.
    System roles (OwnerAdmin, ResellerAdmin, etc.) cannot be deleted or modified.
    
    Attributes:
        organization_id: Parent organization UUID
        name: Role name (unique per organization)
        description: Role description
        permissions: Set of permission strings
        is_system: Whether this is a built-in system role
    """
    
    # System role names (immutable)
    OWNER_ADMIN = "OwnerAdmin"
    RESELLER_ADMIN = "ResellerAdmin"
    TENANT_ADMIN = "TenantAdmin"
    AGENT = "Agent"
    READ_ONLY = "ReadOnly"
    
    SYSTEM_ROLES = {OWNER_ADMIN, RESELLER_ADMIN, TENANT_ADMIN, AGENT, READ_ONLY}
    
    def __init__(
        self,
        id: UUID,
        organization_id: UUID,
        name: str,
        description: Optional[str] = None,
        permissions: Optional[Set[Permission]] = None,
        is_system: bool = False,
        created_at: Optional[datetime] = None,
        updated_at: Optional[datetime] = None,
    ) -> None:
        super().__init__(id, created_at=created_at, updated_at=updated_at)
        self._organization_id = organization_id
        self._name = name
        self._description = description
        self._permissions = permissions or set()
        self._is_system = is_system
    
    @staticmethod
    def create(
        id: UUID,
        organization_id: UUID,
        name: str,
        description: Optional[str] = None,
        permissions: Optional[Set[Permission]] = None,
        is_system: bool = False,
    ) -> Role:
        """
        Factory method to create a new role.
        
        Args:
            id: Role UUID
            organization_id: Organization UUID
            name: Role name
            description: Role description
            permissions: Initial permissions
            is_system: Whether this is a system role
            
        Returns:
            New Role instance with CreatedEvent raised
        """
        role = Role(
            id=id,
            organization_id=organization_id,
            name=name,
            description=description,
            permissions=permissions or set(),
            is_system=is_system,
        )
        
        role.raise_event(
            RoleCreatedEvent(
                role_id=id,
                organization_id=organization_id,
                name=name,
                is_system=is_system,
                permissions=[p.value for p in (permissions or set())],
            )
        )
        
        return role
    
    def grant_permission(self, permission: Permission) -> None:
        """
        Grant a permission to this role.
        
        Args:
            permission: Permission to grant
            
        Raises:
            PermissionDeniedException: If role is a system role
        """
        if self._is_system:
            raise PermissionDeniedException(
                f"Cannot modify permissions on system role: {self._name}"
            )
        
        if permission in self._permissions:
            return  # Already granted
        
        self._permissions.add(permission)
        self._touch()
        
        self.raise_event(
            PermissionGrantedEvent(
                role_id=self.id,
                organization_id=self._organization_id,
                role_name=self._name,
                permission=permission.value,
            )
        )
    
    def revoke_permission(self, permission: Permission) -> None:
        """
        Revoke a permission from this role.
        
        Args:
            permission: Permission to revoke
            
        Raises:
            PermissionDeniedException: If role is a system role
        """
        if self._is_system:
            raise PermissionDeniedException(
                f"Cannot modify permissions on system role: {self._name}"
            )
        
        if permission not in self._permissions:
            return  # Not granted
        
        self._permissions.remove(permission)
        self._touch()
        
        self.raise_event(
            PermissionRevokedEvent(
                role_id=self.id,
                organization_id=self._organization_id,
                role_name=self._name,
                permission=permission.value,
            )
        )
    
    def has_permission(self, permission: Permission) -> bool:
        """Check if role has a specific permission"""
        return permission in self._permissions
    
    def has_any_permission(self, *permissions: Permission) -> bool:
        """Check if role has any of the specified permissions"""
        return any(p in self._permissions for p in permissions)
    
    def has_all_permissions(self, *permissions: Permission) -> bool:
        """Check if role has all of the specified permissions"""
        return all(p in self._permissions for p in permissions)
    
    def update_description(self, description: str) -> None:
        """Update role description"""
        if self._is_system:
            raise PermissionDeniedException(
                f"Cannot modify system role: {self._name}"
            )
        
        self._description = description
        self._touch()
    
    # Properties
    @property
    def organization_id(self) -> UUID:
        return self._organization_id
    
    @property
    def name(self) -> str:
        return self._name
    
    @property
    def description(self) -> Optional[str]:
        return self._description
    
    @property
    def permissions(self) -> Set[Permission]:
        return self._permissions.copy()  # Return copy to prevent mutation
    
    @property
    def is_system(self) -> bool:
        return self._is_system
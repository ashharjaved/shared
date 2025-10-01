# src/identity/domain/entities/user.py

from dataclasses import dataclass
from datetime import datetime
from typing import Optional
from uuid import UUID

from src.identity.domain.value_objects.role import Role


@dataclass(frozen=True)
class User:
    """
    Domain entity representing a user in the system.
    
    Users belong to a specific tenant and have a role that determines
    their permissions within that tenant.
    """
    id: UUID
    tenant_id: UUID
    email: str
    password_hash: str
    role: Role
    is_active: bool
    is_verified: bool
    failed_login_attempts: int
    last_login: Optional[datetime]
    created_at: Optional[datetime]
    updated_at: Optional[datetime]
    
    def __post_init__(self) -> None:
        """Validate user invariants."""
        if not self.email or "@" not in self.email:
            raise ValueError("Invalid email address")
            
        if not self.password_hash:
            raise ValueError("Password hash cannot be empty")
        if self.password_hash is None:
            # Allow None for passwordless users; otherwise enforce non-empty
            pass
        if self.failed_login_attempts < 0:
            raise ValueError("Failed login attempts cannot be negative")
    
    def is_locked_at(self, threshold: int) -> bool:
        """Check if user account is locked using a supplied threshold."""
        return self.failed_login_attempts >= threshold
    
    def can_login(self, lock_threshold: int = 5) -> bool:
        """Check if user can login (active, verified, not locked)."""
        return self.is_active and self.is_verified and not self.is_locked_at(lock_threshold)
    
    def is_super_admin(self) -> bool:
        """Check if user has super admin privileges."""
        return self.role == Role.SUPER_ADMIN
    
    def is_tenant_admin(self) -> bool:
        """Check if user is an admin for their tenant."""
        return self.role in (Role.SUPER_ADMIN, Role.RESELLER_ADMIN, Role.TENANT_ADMIN)
    
    def can_manage_role(self, target_role: Role) -> bool:
        """Check if this user can manage the target role."""
        from src.identity.domain.services import RbacPolicy
        return self.role.can_manage_role(target_role)
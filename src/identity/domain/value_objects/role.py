# src/identity/domain/value_objects/role.py
"""Role value object with hierarchy management."""

from enum import IntEnum, StrEnum
from typing import Self

from ..exception import ValidationError


class RoleHierarchy(IntEnum):
    """Hierarchy levels for roles, where lower value means higher privilege."""
    SUPER_ADMIN = 0
    RESELLER_ADMIN = 1
    TENANT_ADMIN = 2
    TENANT_USER = 3
    READ_ONLY = 4


class Role(StrEnum):
    """Role value object with hierarchy, where lower hierarchy level = higher privilege."""
    
    SUPER_ADMIN = "SUPER_ADMIN"
    RESELLER_ADMIN = "RESELLER_ADMIN"
    TENANT_ADMIN = "TENANT_ADMIN"
    TENANT_USER = "TENANT_USER"
    READ_ONLY = "READ_ONLY"
    
    def hierarchy_level(self) -> int:
        """Return the hierarchy level of this role (0 = highest privilege)."""
        return RoleHierarchy[self.name].value
    
    def can_manage_role(self, other: Self) -> bool:
        """Check if this role can manage another role based on hierarchy."""
        return self.hierarchy_level() < other.hierarchy_level()
    
    def is_at_least(self, required: Self) -> bool:
        """Check if this role meets or exceeds the required role's privilege level."""
        return self.hierarchy_level() <= required.hierarchy_level()
    
    def is_admin(self) -> bool:
        """Check if this role has administrative privileges."""
        return self in {Role.SUPER_ADMIN, Role.RESELLER_ADMIN, Role.TENANT_ADMIN}
    
    @classmethod
    def from_string(cls, role_str: str) -> Self:
        """Create a Role instance from a string."""
        try:
            return cls[role_str.upper()]
        except KeyError:
            valid_roles = [role.name for role in cls]
            raise ValidationError(f"Invalid role: {role_str}. Valid roles: {valid_roles}")
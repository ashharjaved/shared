# src/identity/domain/value_objects/role.py
"""Role value object with hierarchy."""

from enum import IntEnum
from typing import Self

from ..errors import ValidationError


class Role(IntEnum):
    """Role hierarchy with lower index = higher privilege."""
    
    SUPER_ADMIN = 0
    RESELLER_ADMIN = 1
    TENANT_ADMIN = 2
    STAFF = 3
    READ_ONLY = 4
    
    def hierarchy_level(self) -> int:
        """Return hierarchy level (0 = highest privilege)."""
        return self.value
    
    def can_manage_role(self, other: Self) -> bool:
        """Check if this role can manage another role."""
        return self.value < other.value
    
    def is_at_least(self, required: Self) -> bool:
        """Check if this role meets minimum requirement."""
        return self.value <= required.value
    
    def is_admin(self) -> bool:
        """Check if role has admin privileges."""
        return self in {Role.SUPER_ADMIN, Role.RESELLER_ADMIN, Role.TENANT_ADMIN}
    
    @classmethod
    def from_string(cls, role_str: str) -> Self:
        """Create Role from string."""
        try:
            return cls[role_str.upper()]
        except KeyError:
            valid_roles = [role.name for role in cls]
            raise ValidationError(f"Invalid role: {role_str}. Valid roles: {valid_roles}")

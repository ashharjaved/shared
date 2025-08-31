# src/shared/roles.py

from enum import Enum
from typing import List
from typing import List, Callable, Optional

class Role(str, Enum):
    """
    User roles in the system with hierarchical permissions.
    
    Hierarchy (highest to lowest):
    - SUPER_ADMIN: Platform-level admin, can manage everything
    - RESELLER_ADMIN: Can manage reseller tenant and create client tenants
    - TENANT_ADMIN: Can manage their tenant and its users
    - STAFF: Regular user with limited permissions
    """
    SUPER_ADMIN = "SUPER_ADMIN"
    RESELLER_ADMIN = "RESELLER_ADMIN"
    TENANT_ADMIN = "TENANT_ADMIN"
    STAFF = "STAFF"


# Role hierarchy levels 
_ROLE_HIERARCHY = {
    Role.SUPER_ADMIN: 100,
    Role.RESELLER_ADMIN: 80,
    Role.TENANT_ADMIN: 60,
    Role.STAFF: 10,
}


def get_role_level(role: Role) -> int:
    """Get the hierarchy level of a role."""
    return _ROLE_HIERARCHY[role]


def has_min_role(actual_role: Role, required_role: Role) -> bool:
    """
    Check if actual_role has at least the privileges of required_role.
    
    Args:
        actual_role: The role to check
        required_role: The minimum required role
        
    Returns:
        True if actual_role >= required_role in the hierarchy
    """
    return _ROLE_HIERARCHY.get(actual_role, 0) >= _ROLE_HIERARCHY.get(required_role, 0)

def can_manage(actor_role: Role, target_role: Role) -> bool:
    """
    Check if actor can manage (create, update, delete) users with target_role.
    
    Rules:
    - SUPER_ADMIN can manage all roles
    - RESELLER_ADMIN can manage TENANT_ADMIN and STAFF in their tenant tree
    - TENANT_ADMIN can manage STAFF in their tenant
    - STAFF cannot manage any roles
    
    Args:
        actor_role: The role of the user performing the action
        target_role: The role being managed
        
    Returns:
        True if actor can manage target_role
    """
    if actor_role == Role.SUPER_ADMIN:
        return True
    
    if actor_role == Role.RESELLER_ADMIN:
        return target_role in (Role.TENANT_ADMIN, Role.STAFF)
    
    if actor_role == Role.TENANT_ADMIN:
        return target_role == Role.STAFF
    
    # STAFF cannot manage any roles
    return False

def can_manage_user(
    requester_role: Role,
    requester_tenant: str,
    target_role: Role,
    target_tenant: str,
    *,
    reseller_hierarchy_check: Optional[Callable[[str, str], bool]] = None  # optional callback to verify tree
) -> bool:
    """
    Enforce hierarchy rules across tenants.
    - SUPER_ADMIN can manage anyone.
    - RESELLER_ADMIN can manage TENANT_ADMIN/STAFF within its reseller tree.
    - TENANT_ADMIN can manage STAFF within same tenant.
    - STAFF cannot manage anyone.
    """
    if requester_role == Role.SUPER_ADMIN:
        return True

    if requester_role == Role.RESELLER_ADMIN:
        if reseller_hierarchy_check and reseller_hierarchy_check(requester_tenant, target_tenant):
            return _ROLE_HIERARCHY[Role.RESELLER_ADMIN] > _ROLE_HIERARCHY[target_role]
        return False

    if requester_role == Role.TENANT_ADMIN and requester_tenant == target_tenant:
        return target_role == Role.STAFF

    return False

def get_manageable_roles(actor_role: Role) -> List[Role]:
    """
    Get list of roles that the actor can manage.
    
    Args:
        actor_role: The role of the acting user
        
    Returns:
        List of roles that can be managed by actor_role
    """
    manageable = []
    
    for role in Role:
        if can_manage(actor_role, role):
            manageable.append(role)
    
    return manageable


def get_creatable_roles(actor_role: Role) -> List[Role]:
    """
    Get list of roles that the actor can assign when creating users.
    
    Args:
        actor_role: The role of the acting user
        
    Returns:
        List of roles that can be assigned by actor_role
    """
    # For user creation, same rules as management apply
    return get_manageable_roles(actor_role)
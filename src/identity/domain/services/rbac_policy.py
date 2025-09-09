# src/identity/domain/services/rbac_policy.py
"""RBAC policy domain service."""

from ..value_objects.role import Role
from ..errors import UnauthorizedDomainAction


class RbacPolicy:
    """Role-based access control policy service."""
    
    @staticmethod
    def is_at_least(actor_roles: list[Role], required: Role) -> bool:
        """Check if actor has at least the required role level."""
        if not actor_roles:
            return False
        
        highest_role = min(actor_roles)  # Lower enum value = higher privilege
        return highest_role.is_at_least(required)
    
    @staticmethod
    def can_manage_role(actor_roles: list[Role], target_role: Role) -> bool:
        """Check if actor can manage users with target role."""
        if not actor_roles:
            return False
        
        highest_role = min(actor_roles)  # Lower enum value = higher privilege
        return highest_role.can_manage_role(target_role)
    
    @staticmethod
    def can_manage_user_roles(actor_roles: list[Role], target_roles: list[Role]) -> bool:
        """Check if actor can manage user with target roles."""
        if not target_roles:
            return True  # Can manage users with no roles
        
        # Must be able to manage all target roles
        return all(
            RbacPolicy.can_manage_role(actor_roles, target_role)
            for target_role in target_roles
        )
    
    @staticmethod
    def require_at_least(actor_roles: list[Role], required: Role) -> None:
        """Require actor to have at least the specified role level."""
        if not RbacPolicy.is_at_least(actor_roles, required):
            role_names = [role.name for role in actor_roles]
            raise UnauthorizedDomainAction(
                f"Insufficient privileges. Required: {required.name}, Have: {role_names}"
            )
    
    @staticmethod
    def require_can_manage(actor_roles: list[Role], target_role: Role) -> None:
        """Require actor to be able to manage target role."""
        if not RbacPolicy.can_manage_role(actor_roles, target_role):
            role_names = [role.name for role in actor_roles]
            raise UnauthorizedDomainAction(
                f"Cannot manage {target_role.name} role. Actor roles: {role_names}"
            )
    
    @staticmethod
    def get_manageable_roles(actor_roles: list[Role]) -> list[Role]:
        """Get list of roles that actor can manage."""
        if not actor_roles:
            return []
        
        highest_role = min(actor_roles)
        return [role for role in Role if highest_role.can_manage_role(role)]
    
    @staticmethod
    def is_admin(actor_roles: list[Role]) -> bool:
        """Check if actor has admin privileges."""
        return any(role.is_admin() for role in actor_roles)

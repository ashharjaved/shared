"""
Role Service
Orchestrates role and permission management
"""
from __future__ import annotations

from typing import Optional
from uuid import UUID

from shared.domain.result import Result
from shared.infrastructure.observability.logger import get_logger

from src.identity.application.commands.assign_role_command import (
    AssignRoleCommand,
    AssignRoleCommandHandler,
)
from src.identity.application.commands.revoke_role_command import (
    RevokeRoleCommand,
    RevokeRoleCommandHandler,
)
from src.identity.application.queries.get_user_roles_query import (
    GetUserRolesQuery,
    GetUserRolesQueryHandler,
)
from src.identity.application.dto.role_dto import RoleDTO
from src.identity.infrastructure.adapters.identity_unit_of_work import (
    IdentityUnitOfWork,
)

logger = get_logger(__name__)


class RoleService:
    """
    Role service for RBAC operations.
    
    Orchestrates role assignment and permission management.
    """
    
    def __init__(self, uow: IdentityUnitOfWork) -> None:
        self.uow = uow
    
    async def assign_role(
        self,
        user_id: UUID,
        role_id: UUID,
        organization_id: UUID,
        assigned_by: Optional[UUID] = None,
    ) -> Result[UUID, str]:
        """
        Assign a role to a user.
        
        Args:
            user_id: Target user UUID
            role_id: Role UUID to assign
            organization_id: Organization UUID (for RLS)
            assigned_by: User ID performing the assignment
            
        Returns:
            Result with user_role ID or error message
        """
        command = AssignRoleCommand(
            user_id=user_id,
            role_id=role_id,
            organization_id=organization_id,
            assigned_by=assigned_by,
        )
        
        handler = AssignRoleCommandHandler(self.uow)
        return await handler.handle(command)
    
    async def revoke_role(
        self,
        user_id: UUID,
        role_id: UUID,
        organization_id: UUID,
        revoked_by: Optional[UUID] = None,
    ) -> Result[bool, str]:
        """
        Revoke a role from a user.
        
        Args:
            user_id: Target user UUID
            role_id: Role UUID to revoke
            organization_id: Organization UUID (for RLS)
            revoked_by: User ID performing the revocation
            
        Returns:
            Result with success boolean or error message
        """
        command = RevokeRoleCommand(
            user_id=user_id,
            role_id=role_id,
            organization_id=organization_id,
            revoked_by=revoked_by,
        )
        
        handler = RevokeRoleCommandHandler(self.uow)
        return await handler.handle(command)
    
    async def get_user_roles(
        self,
        user_id: UUID,
        organization_id: UUID,
    ) -> Result[list[RoleDTO], str]:
        """
        Get all roles assigned to a user.
        
        Args:
            user_id: User UUID
            organization_id: Organization UUID (for RLS)
            
        Returns:
            Result with list of RoleDTOs
        """
        query = GetUserRolesQuery(
            user_id=user_id,
            organization_id=organization_id,
        )
        
        handler = GetUserRolesQueryHandler(self.uow)
        return await handler.handle(query)
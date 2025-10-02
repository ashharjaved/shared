"""
Assign Role Command
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional
from uuid import UUID, uuid4

from shared.application.base_command import BaseCommand
from shared.application.command_handler import CommandHandler
from shared.domain.result import Result, Success, Failure
from shared.infrastructure.observability.logger import get_logger

from src.identity.domain.entities.user_role import UserRole
from src.identity.infrastructure.adapters.identity_unit_of_work import (
    IdentityUnitOfWork,
)
from src.identity.infrastructure.services.audit_log_service import AuditLogService

logger = get_logger(__name__)


@dataclass(frozen=True)
class AssignRoleCommand(BaseCommand):
    """
    Command to assign a role to a user.
    
    Attributes:
        user_id: Target user UUID
        role_id: Role UUID to assign
        organization_id: Organization UUID (for RLS)
        assigned_by: User ID who is assigning the role
    """
    user_id: UUID
    role_id: UUID
    organization_id: UUID
    assigned_by: Optional[UUID] = None


class AssignRoleCommandHandler(CommandHandler[AssignRoleCommand, UUID]):
    """
    Handler for AssignRoleCommand.
    
    Assigns a role to a user and logs the action.
    """
    
    def __init__(self, uow: IdentityUnitOfWork) -> None:
        self.uow = uow
    
    async def handle(self, command: AssignRoleCommand) -> Result[UUID, str]:
        """
        Execute role assignment.
        
        Args:
            command: Assign role command
            
        Returns:
            Result with user_role ID or error message
        """
        try:
            async with self.uow:
                # Set RLS context
                self.uow.set_tenant_context(
                    organization_id=command.organization_id,
                    user_id=command.assigned_by,
                )
                
                # Verify user exists
                user = await self.uow.users.get_by_id(command.user_id)
                if not user:
                    return Failure(f"User not found: {command.user_id}")
                
                # Verify role exists
                role = await self.uow.roles.get_by_id(command.role_id)
                if not role:
                    return Failure(f"Role not found: {command.role_id}")
                
                # Check if already assigned
                existing_roles = await self.uow.user_roles.find_by_user(command.user_id)
                if any(ur.role_id == command.role_id for ur in existing_roles):
                    return Failure(f"User already has role: {role.name}")
                
                # Create user-role assignment
                user_role = UserRole.create(
                    id=uuid4(),
                    user_id=command.user_id,
                    role_id=command.role_id,
                    granted_by=command.assigned_by,
                )
                
                saved = await self.uow.user_roles.add(user_role)
                
                # Write audit log
                audit_service = AuditLogService(self.uow.audit_logs)
                await audit_service.log_role_assigned(
                    user_id=command.user_id,
                    role_id=command.role_id,
                    organization_id=command.organization_id,
                    role_name=role.name,
                    assigned_by=command.assigned_by,
                )
                
                await self.uow.commit()
                
                logger.info(
                    f"Role assigned: {role.name} to user {command.user_id}",
                    extra={
                        "user_id": str(command.user_id),
                        "role_id": str(command.role_id),
                        "assigned_by": str(command.assigned_by) if command.assigned_by else None,
                    },
                )
                
                return Success(saved.id)
                
        except Exception as e:
            logger.error(
                f"Failed to assign role: {e}",
                extra={"command": command, "error": str(e)},
            )
            return Failure(f"Failed to assign role: {str(e)}")
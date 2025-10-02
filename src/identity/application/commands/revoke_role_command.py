"""
Revoke Role Command
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional
from uuid import UUID

from shared.application.base_command import BaseCommand
from shared.application.command_handler import CommandHandler
from shared.domain.result import Result, Success, Failure
from shared.infrastructure.observability.logger import get_logger

from src.identity.infrastructure.adapters.identity_unit_of_work import (
    IdentityUnitOfWork,
)
from src.identity.infrastructure.services.audit_log_service import AuditLogService

logger = get_logger(__name__)


@dataclass(frozen=True)
class RevokeRoleCommand(BaseCommand):
    """
    Command to revoke a role from a user.
    
    Attributes:
        user_id: Target user UUID
        role_id: Role UUID to revoke
        organization_id: Organization UUID (for RLS)
        revoked_by: User ID who is revoking the role
    """
    user_id: UUID
    role_id: UUID
    organization_id: UUID
    revoked_by: Optional[UUID] = None


class RevokeRoleCommandHandler(CommandHandler[RevokeRoleCommand, bool]):
    """
    Handler for RevokeRoleCommand.
    
    Revokes a role from a user and logs the action.
    """
    
    def __init__(self, uow: IdentityUnitOfWork) -> None:
        self.uow = uow
    
    async def handle(self, command: RevokeRoleCommand) -> Result[bool, str]:
        """
        Execute role revocation.
        
        Args:
            command: Revoke role command
            
        Returns:
            Result with success boolean or error message
        """
        try:
            async with self.uow:
                # Set RLS context
                self.uow.set_tenant_context(
                    organization_id=command.organization_id,
                    user_id=command.revoked_by,
                )
                
                # Verify role exists
                role = await self.uow.roles.get_by_id(command.role_id)
                if not role:
                    return Failure(f"Role not found: {command.role_id}")
                
                # Find user-role assignment
                user_roles = await self.uow.user_roles.find_by_user(command.user_id)
                user_role = next((ur for ur in user_roles if ur.role_id == command.role_id), None)
                
                if not user_role:
                    return Failure(f"User does not have role: {role.name}")
                
                # Delete user-role assignment
                await self.uow.user_roles.delete(user_role.id)
                
                # Write audit log
                audit_service = AuditLogService(self.uow.audit_logs)
                await audit_service.log_role_revoked(
                    user_id=command.user_id,
                    role_id=command.role_id,
                    organization_id=command.organization_id,
                    role_name=role.name,
                    revoked_by=command.revoked_by,
                )
                
                await self.uow.commit()
                
                logger.info(
                    f"Role revoked: {role.name} from user {command.user_id}",
                    extra={
                        "user_id": str(command.user_id),
                        "role_id": str(command.role_id),
                        "revoked_by": str(command.revoked_by) if command.revoked_by else None,
                    },
                )
                
                return Success(True)
                
        except Exception as e:
            logger.error(
                f"Failed to revoke role: {e}",
                extra={"command": command, "error": str(e)},
            )
            return Failure(f"Failed to revoke role: {str(e)}")
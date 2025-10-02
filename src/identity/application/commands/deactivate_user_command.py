"""
Deactivate User Command
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
class DeactivateUserCommand(BaseCommand):
    """
    Command to deactivate a user account.
    
    Attributes:
        user_id: User UUID to deactivate
        organization_id: Organization UUID (for RLS)
        deactivated_by: User ID performing the deactivation
        reason: Optional deactivation reason
    """
    user_id: UUID
    organization_id: UUID
    deactivated_by: Optional[UUID] = None
    reason: Optional[str] = None


class DeactivateUserCommandHandler(CommandHandler[DeactivateUserCommand, bool]):
    """
    Handler for DeactivateUserCommand.
    
    Deactivates user and revokes all active sessions.
    """
    
    def __init__(self, uow: IdentityUnitOfWork) -> None:
        self.uow = uow
    
    async def handle(self, command: DeactivateUserCommand) -> Result[bool, str]:
        """
        Execute user deactivation.
        
        Args:
            command: Deactivate user command
            
        Returns:
            Result with success boolean or error message
        """
        try:
            async with self.uow:
                # Set RLS context
                self.uow.set_tenant_context(
                    organization_id=command.organization_id,
                    user_id=command.deactivated_by,
                )
                
                # Get user
                user = await self.uow.users.get_by_id(command.user_id)
                if not user:
                    return Failure(f"User not found: {command.user_id}")
                
                # Check if already deactivated
                if not user.is_active:
                    return Failure("User already deactivated")
                
                # Deactivate user
                user.deactivate()
                await self.uow.users.update(user)
                self.uow.track_aggregate(user)
                
                # Revoke all refresh tokens (force logout)
                await self.uow.refresh_tokens.revoke_all_for_user(command.user_id)
                
                # Write audit log
                audit_service = AuditLogService(self.uow.audit_logs)
                await audit_service.log(
                    action="user_deactivated",
                    organization_id=command.organization_id,
                    user_id=command.deactivated_by,
                    resource_type="user",
                    resource_id=command.user_id,
                    metadata={
                        "target_user_email": str(user.email),
                        "reason": command.reason,
                    },
                )
                
                await self.uow.commit()
                
                logger.info(
                    f"User deactivated: {command.user_id}",
                    extra={
                        "user_id": str(command.user_id),
                        "deactivated_by": str(command.deactivated_by) if command.deactivated_by else None,
                        "reason": command.reason,
                    },
                )
                
                return Success(True)
                
        except Exception as e:
            logger.error(
                f"Failed to deactivate user: {e}",
                extra={"command": command, "error": str(e)},
            )
            return Failure(f"Failed to deactivate user: {str(e)}")
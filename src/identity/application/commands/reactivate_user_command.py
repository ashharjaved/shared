"""
Reactivate User Command
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
class ReactivateUserCommand(BaseCommand):
    """
    Command to reactivate a user account.
    
    Attributes:
        user_id: User UUID to reactivate
        organization_id: Organization UUID (for RLS)
        reactivated_by: User ID performing the reactivation
    """
    user_id: UUID
    organization_id: UUID
    reactivated_by: Optional[UUID] = None


class ReactivateUserCommandHandler(CommandHandler[ReactivateUserCommand, bool]):
    """
    Handler for ReactivateUserCommand.
    
    Reactivates a previously deactivated user.
    """
    
    def __init__(self, uow: IdentityUnitOfWork) -> None:
        self.uow = uow
    
    async def handle(self, command: ReactivateUserCommand) -> Result[bool, str]:
        """
        Execute user reactivation.
        
        Args:
            command: Reactivate user command
            
        Returns:
            Result with success boolean or error message
        """
        try:
            async with self.uow:
                # Set RLS context
                self.uow.set_tenant_context(
                    organization_id=command.organization_id,
                    user_id=command.reactivated_by,
                )
                
                # Get user
                user = await self.uow.users.get_by_id(command.user_id)
                if not user:
                    return Failure(f"User not found: {command.user_id}")
                
                # Check if already active
                if user.is_active:
                    return Failure("User already active")
                
                # Reactivate user
                user.reactivate()
                await self.uow.users.update(user)
                self.uow.track_aggregate(user)
                
                # Write audit log
                audit_service = AuditLogService(self.uow.audit_logs)
                await audit_service.log(
                    action="user_reactivated",
                    organization_id=command.organization_id,
                    user_id=command.reactivated_by,
                    resource_type="user",
                    resource_id=command.user_id,
                    metadata={
                        "target_user_email": str(user.email),
                    },
                )
                
                await self.uow.commit()
                
                logger.info(
                    f"User reactivated: {command.user_id}",
                    extra={
                        "user_id": str(command.user_id),
                        "reactivated_by": str(command.reactivated_by) if command.reactivated_by else None,
                    },
                )
                
                return Success(True)
                
        except Exception as e:
            logger.error(
                f"Failed to reactivate user: {e}",
                extra={"command": command, "error": str(e)},
            )
            return Failure(f"Failed to reactivate user: {str(e)}")
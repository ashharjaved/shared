"""
Update Password Command
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional
from uuid import UUID

from shared.application.base_command import BaseCommand
from shared.application.command_handler import CommandHandler
from shared.domain.result import Result, Success, Failure
from shared.infrastructure.observability.logger import get_logger

from src.identity.domain.value_objects.password_hash import PasswordHash
from src.identity.infrastructure.adapters.identity_unit_of_work import (
    IdentityUnitOfWork,
)
from src.identity.infrastructure.services.audit_log_service import AuditLogService

logger = get_logger(__name__)


@dataclass(frozen=True)
class UpdatePasswordCommand(BaseCommand):
    """
    Command to update user password.
    
    Attributes:
        user_id: User UUID
        new_password: New plain text password
        organization_id: Organization UUID (for RLS)
        changed_by: User ID performing the change (for audit)
        ip_address: Client IP (for audit)
    """
    user_id: UUID
    new_password: str
    organization_id: UUID
    changed_by: Optional[UUID] = None
    ip_address: Optional[str] = None


class UpdatePasswordCommandHandler(CommandHandler[UpdatePasswordCommand, bool]):
    """
    Handler for UpdatePasswordCommand.
    
    Updates user password and logs the action.
    """
    
    def __init__(self, uow: IdentityUnitOfWork) -> None:
        self.uow = uow
    
    async def handle(self, command: UpdatePasswordCommand) -> Result[bool, str]:
        """
        Execute password update.
        
        Args:
            command: Update password command
            
        Returns:
            Result with success boolean or error message
        """
        try:
            async with self.uow:
                # Set RLS context
                self.uow.set_tenant_context(
                    organization_id=command.organization_id,
                    user_id=command.changed_by,
                )
                
                # Get user
                user = await self.uow.users.get_by_id(command.user_id)
                if not user:
                    return Failure(f"User not found: {command.user_id}")
                
                # Hash new password
                try:
                    new_password_hash = PasswordHash.from_plain_text(command.new_password)
                except ValueError as e:
                    return Failure(f"Invalid password: {str(e)}")
                
                # Update password
                user.update_password(new_password_hash, changed_by=command.changed_by)
                
                # Persist
                await self.uow.users.update(user)
                self.uow.track_aggregate(user)
                
                # Revoke all refresh tokens (force re-login on all devices)
                await self.uow.refresh_tokens.revoke_all_for_user(command.user_id)
                
                # Write audit log
                audit_service = AuditLogService(self.uow.audit_logs)
                await audit_service.log_password_changed(
                    user_id=command.user_id,
                    organization_id=command.organization_id,
                    changed_by=command.changed_by,
                    ip_address=command.ip_address,
                )
                
                await self.uow.commit()
                
                logger.info(
                    f"Password updated for user {command.user_id}",
                    extra={
                        "user_id": str(command.user_id),
                        "changed_by": str(command.changed_by) if command.changed_by else None,
                    },
                )
                
                return Success(True)
                
        except Exception as e:
            logger.error(
                f"Failed to update password: {e}",
                extra={"command": command, "error": str(e)},
            )
            return Failure(f"Failed to update password: {str(e)}")
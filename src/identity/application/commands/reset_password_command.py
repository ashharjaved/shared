"""
Reset Password Command
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from shared.application.base_command import BaseCommand
from shared.application.command_handler import CommandHandler
from shared.domain.result import Result, Success, Failure
from shared.infrastructure.observability.logger import get_logger

from src.identity.domain.value_objects.password_hash import PasswordHash
from src.identity.domain.exception import (
    PasswordResetTokenExpiredException,
    PasswordResetTokenAlreadyUsedException,
)
from src.identity.infrastructure.adapters.identity_unit_of_work import (
    IdentityUnitOfWork,
)
from src.identity.infrastructure.services.audit_log_service import AuditLogService

logger = get_logger(__name__)


@dataclass(frozen=True)
class ResetPasswordCommand(BaseCommand):
    """
    Command to reset password using token.
    
    Attributes:
        reset_token: Plain reset token string
        new_password: New plain text password
        ip_address: Client IP (for audit)
    """
    reset_token: str
    new_password: str
    ip_address: Optional[str] = None


class ResetPasswordCommandHandler(CommandHandler[ResetPasswordCommand, bool]):
    """
    Handler for ResetPasswordCommand.
    
    Validates token, updates password, and revokes all sessions.
    """
    
    def __init__(self, uow: IdentityUnitOfWork) -> None:
        self.uow = uow
    
    async def handle(self, command: ResetPasswordCommand) -> Result[bool, str]:
        """
        Execute password reset.
        
        Args:
            command: Reset password command
            
        Returns:
            Result with success boolean or error message
        """
        try:
            async with self.uow:
                # Hash token to look it up
                import hashlib
                token_hash = hashlib.sha256(command.reset_token.encode()).hexdigest()
                
                # Find reset token
                reset_token = await self.uow.password_reset_tokens.get_by_hash(token_hash)
                if not reset_token:
                    logger.warning("Password reset token not found")
                    return Failure("Invalid reset token")
                
                # Verify token validity
                try:
                    reset_token.verify(command.reset_token)
                except PasswordResetTokenExpiredException:
                    logger.warning(
                        f"Expired reset token used: {reset_token.id}",
                        extra={"token_id": str(reset_token.id)},
                    )
                    return Failure("Reset token has expired")
                except PasswordResetTokenAlreadyUsedException:
                    logger.warning(
                        f"Already used reset token: {reset_token.id}",
                        extra={"token_id": str(reset_token.id)},
                    )
                    return Failure("Reset token already used")
                except ValueError:
                    return Failure("Invalid reset token")
                
                # Get user
                user = await self.uow.users.get_by_id(reset_token.user_id)
                if not user:
                    return Failure("User not found")
                
                # Set RLS context
                self.uow.set_tenant_context(
                    organization_id=user.organization_id,
                    user_id=user.id,
                )
                
                # Hash new password
                try:
                    new_password_hash = PasswordHash.from_plain_text(command.new_password)
                except ValueError as e:
                    return Failure(f"Invalid password: {str(e)}")
                
                # Update password
                user.update_password(new_password_hash, changed_by=None)
                await self.uow.users.update(user)
                self.uow.track_aggregate(user)
                
                # Mark token as used
                reset_token.mark_as_used()
                await self.uow.password_reset_tokens.update(reset_token)
                
                # Revoke all refresh tokens (force logout on all devices)
                await self.uow.refresh_tokens.revoke_all_for_user(user.id)
                
                # Write audit log
                audit_service = AuditLogService(self.uow.audit_logs)
                await audit_service.log(
                    action="password_reset",
                    organization_id=user.organization_id,
                    user_id=user.id,
                    resource_type="user",
                    resource_id=user.id,
                    metadata={
                        "email": str(user.email),
                        "ip_address": command.ip_address,
                    },
                )
                
                await self.uow.commit()
                
                logger.info(
                    f"Password reset for user {user.id}",
                    extra={
                        "user_id": str(user.id),
                        "email": str(user.email),
                    },
                )
                
                return Success(True)
                
        except Exception as e:
            logger.error(
                f"Password reset failed: {e}",
                extra={"error": str(e)},
            )
            return Failure(f"Password reset failed: {str(e)}")
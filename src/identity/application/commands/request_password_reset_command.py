"""
Request Password Reset Command
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional
from uuid import uuid4

from shared.application.base_command import BaseCommand
from shared.application.command_handler import CommandHandler
from shared.domain.result import Result, Success, Failure
from shared.infrastructure.observability.logger import get_logger

from src.identity.domain.value_objects.email import Email
from src.identity.infrastructure.adapters.identity_unit_of_work import (
    IdentityUnitOfWork,
)
from src.identity.infrastructure.services.audit_log_service import AuditLogService

logger = get_logger(__name__)


@dataclass(frozen=True)
class RequestPasswordResetCommand(BaseCommand):
    """
    Command to request password reset.
    
    Generates reset token and sends email.
    
    Attributes:
        email: User email address
        ip_address: Client IP (for audit)
    """
    email: str
    ip_address: Optional[str] = None


class RequestPasswordResetCommandHandler(CommandHandler[RequestPasswordResetCommand, bool]):
    """
    Handler for RequestPasswordResetCommand.
    
    Creates reset token and sends email (email sending handled by event).
    
    Note: Always returns success to prevent email enumeration attacks.
    """
    
    def __init__(self, uow: IdentityUnitOfWork) -> None:
        self.uow = uow
    
    async def handle(self, command: RequestPasswordResetCommand) -> Result[bool, str]:
        """
        Execute password reset request.
        
        Args:
            command: Request password reset command
            
        Returns:
            Result with success boolean (always true to prevent enumeration)
        """
        try:
            async with self.uow:
                # Validate email format
                try:
                    email = Email(command.email)
                except ValueError:
                    # Return success anyway to prevent email enumeration
                    logger.info(
                        "Password reset requested with invalid email format",
                        extra={"email": command.email},
                    )
                    return Success(True)
                
                # Find user by email (across all orgs, no RLS needed)
                # Note: get_by_email searches across all orgs if no RLS set
                user = await self.uow.users.get_by_email(email)
                
                if not user:
                    # Return success anyway to prevent email enumeration
                    logger.info(
                        f"Password reset requested for non-existent email: {command.email}",
                        extra={"email": command.email},
                    )
                    return Success(True)
                
                # Set RLS context
                self.uow.set_tenant_context(
                    organization_id=user.organization_id,
                )
                
                # Generate reset token
                from src.identity.domain.entities.password_reset_token import (
                    PasswordResetToken,
                )
                
                reset_token, plain_token = PasswordResetToken.create(
                    id=uuid4(),
                    user_id=user.id,
                )
                
                # Persist token
                await self.uow.password_reset_tokens.add(reset_token)
                
                # TODO: Emit domain event PasswordResetRequestedEvent
                # which will be handled by EmailService to send the email
                logger.info(
                    f"Password reset requested for user {user.id}",
                    extra={
                        "user_id": str(user.id),
                        "email": str(user.email),
                        "reset_token": plain_token,  # Don't log in production
                    },
                )
                
                # Write audit log
                audit_service = AuditLogService(self.uow.audit_logs)
                await audit_service.log(
                    action="password_reset_requested",
                    organization_id=user.organization_id,
                    user_id=user.id,
                    resource_type="password_reset",
                    resource_id=reset_token.id,
                    metadata={
                        "email": str(user.email),
                        "ip_address": command.ip_address,
                    },
                )
                
                await self.uow.commit()
                
                logger.info(
                    f"Password reset token created for user {user.id}",
                    extra={
                        "user_id": str(user.id),
                        "token_id": str(reset_token.id),
                    },
                )
                
                # Always return success to prevent email enumeration
                return Success(True)
                
        except Exception as e:
            logger.error(
                f"Failed to request password reset: {e}",
                extra={"command": command, "error": str(e)},
            )
            # Still return success to prevent enumeration
            return Success(True)
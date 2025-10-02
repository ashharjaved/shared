"""
Request Email Verification Command
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional
from uuid import UUID, uuid4

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
class RequestEmailVerificationCommand(BaseCommand):
    """
    Command to request email verification.
    
    Generates a verification token and sends email.
    
    Attributes:
        user_id: User UUID
        organization_id: Organization UUID (for RLS)
        ip_address: Client IP (for audit)
    """
    user_id: UUID
    organization_id: UUID
    ip_address: Optional[str] = None


class RequestEmailVerificationCommandHandler(CommandHandler[RequestEmailVerificationCommand, str]):
    """
    Handler for RequestEmailVerificationCommand.
    
    Creates verification token and sends email (email sending would be
    handled by a domain event subscriber in production).
    """
    
    def __init__(self, uow: IdentityUnitOfWork) -> None:
        self.uow = uow
    
    async def handle(self, command: RequestEmailVerificationCommand) -> Result[str, str]:
        """
        Execute email verification request.
        
        Args:
            command: Request verification command
            
        Returns:
            Result with verification token or error message
        """
        try:
            async with self.uow:
                # Set RLS context
                self.uow.set_tenant_context(
                    organization_id=command.organization_id,
                    user_id=command.user_id,
                )
                
                # Get user
                user = await self.uow.users.get_by_id(command.user_id)
                if not user:
                    return Failure(f"User not found: {command.user_id}")
                
                # Check if already verified
                if user.email_verified:
                    return Failure("Email already verified")
                
                # Generate verification token (using domain method)
                from src.identity.domain.entities.email_verification_token import (
                    EmailVerificationToken,
                )
                
                verification_token, plain_token = EmailVerificationToken.create(
                    id=uuid4(),
                    user_id=user.id,
                    email=str(user.email),
                )
                
                # Persist token
                await self.uow.email_verification_tokens.add(verification_token)
                
                # TODO: Emit domain event EmailVerificationRequestedEvent
                # which will be handled by EmailService to send the email
                # For now, just log
                logger.info(
                    f"Email verification requested for user {user.id}",
                    extra={
                        "user_id": str(user.id),
                        "email": str(user.email),
                        "verification_token": plain_token,  # In production, don't log this
                    },
                )
                
                # Write audit log
                audit_service = AuditLogService(self.uow.audit_logs)
                await audit_service.log(
                    action="email_verification_requested",
                    organization_id=command.organization_id,
                    user_id=command.user_id,
                    resource_type="email_verification",
                    resource_id=verification_token.id,
                    metadata={
                        "email": str(user.email),
                        "ip_address": command.ip_address,
                    },
                )
                
                await self.uow.commit()
                
                logger.info(
                    f"Email verification token created for user {command.user_id}",
                    extra={
                        "user_id": str(command.user_id),
                        "token_id": str(verification_token.id),
                    },
                )
                
                # Return token (in production, this wouldn't be returned,
                # it would be sent via email)
                return Success(plain_token)
                
        except Exception as e:
            logger.error(
                f"Failed to request email verification: {e}",
                extra={"command": command, "error": str(e)},
            )
            return Failure(f"Failed to request email verification: {str(e)}")
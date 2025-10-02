"""
Verify Email Command
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional
from uuid import UUID

from shared.application.base_command import BaseCommand
from shared.application.command_handler import CommandHandler
from shared.domain.result import Result, Success, Failure
from shared.infrastructure.observability.logger import get_logger

from src.identity.domain.exception import (
    EmailVerificationTokenExpiredException,
    EmailVerificationTokenAlreadyUsedException,
)
from src.identity.infrastructure.adapters.identity_unit_of_work import (
    IdentityUnitOfWork,
)
from src.identity.infrastructure.services.audit_log_service import AuditLogService

logger = get_logger(__name__)


@dataclass(frozen=True)
class VerifyEmailCommand(BaseCommand):
    """
    Command to verify email using token.
    
    Attributes:
        verification_token: Plain verification token string
        ip_address: Client IP (for audit)
    """
    verification_token: str
    ip_address: Optional[str] = None


class VerifyEmailCommandHandler(CommandHandler[VerifyEmailCommand, bool]):
    """
    Handler for VerifyEmailCommand.
    
    Validates token and marks email as verified.
    """
    
    def __init__(self, uow: IdentityUnitOfWork) -> None:
        self.uow = uow
    
    async def handle(self, command: VerifyEmailCommand) -> Result[bool, str]:
        """
        Execute email verification.
        
        Args:
            command: Verify email command
            
        Returns:
            Result with success boolean or error message
        """
        try:
            async with self.uow:
                # Hash token to look it up
                import hashlib
                token_hash = hashlib.sha256(command.verification_token.encode()).hexdigest()
                
                # Find verification token
                verification_token = await self.uow.email_verification_tokens.get_by_hash(
                    token_hash
                )
                if not verification_token:
                    logger.warning("Email verification token not found")
                    return Failure("Invalid verification token")
                
                # Verify token validity
                try:
                    verification_token.verify(command.verification_token)
                except EmailVerificationTokenExpiredException:
                    logger.warning(
                        f"Expired verification token used: {verification_token.id}",
                        extra={"token_id": str(verification_token.id)},
                    )
                    return Failure("Verification token has expired")
                except EmailVerificationTokenAlreadyUsedException:
                    logger.warning(
                        f"Already used verification token: {verification_token.id}",
                        extra={"token_id": str(verification_token.id)},
                    )
                    return Failure("Verification token already used")
                except ValueError:
                    return Failure("Invalid verification token")
                
                # Get user
                user = await self.uow.users.get_by_id(verification_token.user_id)
                if not user:
                    return Failure("User not found")
                
                # Set RLS context
                self.uow.set_tenant_context(
                    organization_id=user.organization_id,
                    user_id=user.id,
                )
                
                # Check if already verified
                if user.email_verified:
                    logger.info(
                        f"Email already verified for user {user.id}",
                        extra={"user_id": str(user.id)},
                    )
                    return Success(True)
                
                # Mark email as verified
                user.verify_email()
                await self.uow.users.update(user)
                self.uow.track_aggregate(user)
                
                # Mark token as used
                verification_token.mark_as_used()
                await self.uow.email_verification_tokens.update(verification_token)
                
                # Write audit log
                audit_service = AuditLogService(self.uow.audit_logs)
                await audit_service.log(
                    action="email_verified",
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
                    f"Email verified for user {user.id}",
                    extra={
                        "user_id": str(user.id),
                        "email": str(user.email),
                    },
                )
                
                return Success(True)
                
        except Exception as e:
            logger.error(
                f"Email verification failed: {e}",
                extra={"error": str(e)},
            )
            return Failure(f"Email verification failed: {str(e)}")
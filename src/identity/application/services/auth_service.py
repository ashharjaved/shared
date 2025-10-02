"""
Authentication Service
Orchestrates authentication operations
"""
from __future__ import annotations

from typing import Optional
from uuid import UUID

from shared.domain.result import Result
from shared.infrastructure.observability.logger import get_logger

from src.identity.application.commands.login_command import (
    LoginCommand,
    LoginCommandHandler,
)
from src.identity.application.commands.refresh_token_command import (
    RefreshTokenCommand,
    RefreshTokenCommandHandler,
)
from src.identity.application.dto.auth_dto import LoginResponseDTO
from src.identity.infrastructure.adapters.identity_unit_of_work import (
    IdentityUnitOfWork,
)
from src.identity.infrastructure.adapters.jwt_service import JWTService

logger = get_logger(__name__)


class AuthService:
    """
    Authentication service for login and token management.
    
    Orchestrates authentication-related operations.
    """
    
    def __init__(
        self,
        uow: IdentityUnitOfWork,
        jwt_service: JWTService,
    ) -> None:
        self.uow = uow
        self.jwt_service = jwt_service
    
    async def login(
        self,
        email: str,
        password: str,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> Result[LoginResponseDTO, str]:
        """
        Authenticate user and return tokens.
        
        Args:
            email: User email
            password: Plain text password
            ip_address: Client IP (for audit)
            user_agent: Client user agent (for audit)
            
        Returns:
            Result with LoginResponseDTO or error message
        """
        command = LoginCommand(
            email=email,
            password=password,
            ip_address=ip_address,
            user_agent=user_agent,
        )
        
        handler = LoginCommandHandler(self.uow, self.jwt_service)
        return await handler.handle(command)
    
    async def refresh_token(
        self,
        refresh_token: str,
    ) -> Result[LoginResponseDTO, str]:
        """
        Refresh access token using refresh token.
        
        Args:
            refresh_token: Plain refresh token string
            
        Returns:
            Result with new LoginResponseDTO or error message
        """
        command = RefreshTokenCommand(refresh_token=refresh_token)
        
        handler = RefreshTokenCommandHandler(self.uow, self.jwt_service)
        return await handler.handle(command)
    
    def verify_access_token(self, token: str) -> dict:
        """
        Verify and decode access token.
        
        Args:
            token: JWT access token
            
        Returns:
            Token payload dict
            
        Raises:
            jwt.ExpiredSignatureError: If token expired
            jwt.InvalidTokenError: If token invalid
        """
        return self.jwt_service.verify_access_token(token)
    
    async def request_password_reset(
        self,
        email: str,
        ip_address: Optional[str] = None,
    ) -> Result[bool, str]:
        """
        Request password reset for email.
        
        Always returns success to prevent email enumeration.
        
        Args:
            email: User email address
            ip_address: Client IP (for audit)
            
        Returns:
            Result with success boolean
        """
        from src.identity.application.commands.request_password_reset_command import (
            RequestPasswordResetCommand,
            RequestPasswordResetCommandHandler,
        )
        
        command = RequestPasswordResetCommand(
            email=email,
            ip_address=ip_address,
        )
        
        handler = RequestPasswordResetCommandHandler(self.uow)
        return await handler.handle(command)
    
    async def reset_password(
        self,
        reset_token: str,
        new_password: str,
        ip_address: Optional[str] = None,
    ) -> Result[bool, str]:
        """
        Reset password using reset token.
        
        Args:
            reset_token: Plain reset token string
            new_password: New plain text password
            ip_address: Client IP (for audit)
            
        Returns:
            Result with success boolean or error message
        """
        from src.identity.application.commands.reset_password_command import (
            ResetPasswordCommand,
            ResetPasswordCommandHandler,
        )
        
        command = ResetPasswordCommand(
            reset_token=reset_token,
            new_password=new_password,
            ip_address=ip_address,
        )
        
        handler = ResetPasswordCommandHandler(self.uow)
        return await handler.handle(command)
    
    async def request_email_verification(
        self,
        user_id: UUID,
        organization_id: UUID,
        ip_address: Optional[str] = None,
    ) -> Result[str, str]:
        """
        Request email verification for user.
        
        Args:
            user_id: User UUID
            organization_id: Organization UUID (for RLS)
            ip_address: Client IP (for audit)
            
        Returns:
            Result with verification token or error message
        """
        from src.identity.application.commands.request_email_verification_command import (
            RequestEmailVerificationCommand,
            RequestEmailVerificationCommandHandler,
        )
        
        command = RequestEmailVerificationCommand(
            user_id=user_id,
            organization_id=organization_id,
            ip_address=ip_address,
        )
        
        handler = RequestEmailVerificationCommandHandler(self.uow)
        return await handler.handle(command)
    
    async def verify_email(
        self,
        verification_token: str,
        ip_address: Optional[str] = None,
    ) -> Result[bool, str]:
        """
        Verify email using verification token.
        
        Args:
            verification_token: Plain verification token string
            ip_address: Client IP (for audit)
            
        Returns:
            Result with success boolean or error message
        """
        from src.identity.application.commands.verify_email_command import (
            VerifyEmailCommand,
            VerifyEmailCommandHandler,
        )
        
        command = VerifyEmailCommand(
            verification_token=verification_token,
            ip_address=ip_address,
        )
        
        handler = VerifyEmailCommandHandler(self.uow)
        return await handler.handle(command)
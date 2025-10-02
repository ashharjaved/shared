"""
Login Command
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
from src.identity.domain.exception import (
    InvalidCredentialsException,
    AccountLockedException,
)
from src.identity.infrastructure.adapters.identity_unit_of_work import (
    IdentityUnitOfWork,
)
from src.identity.infrastructure.adapters.jwt_service import JWTService
from src.identity.infrastructure.services.audit_log_service import AuditLogService
from src.identity.application.dto.auth_dto import LoginResponseDTO

logger = get_logger(__name__)


@dataclass(frozen=True)
class LoginCommand(BaseCommand):
    """
    Command to authenticate a user.
    
    Attributes:
        email: User email address
        password: Plain text password
        ip_address: Client IP address (for audit)
        user_agent: Client user agent (for audit)
    """
    email: str
    password: str
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None


class LoginCommandHandler(CommandHandler[LoginCommand, LoginResponseDTO]):
    """
    Handler for LoginCommand.
    
    Authenticates user and returns JWT tokens.
    """
    
    def __init__(
        self,
        uow: IdentityUnitOfWork,
        jwt_service: JWTService,
    ) -> None:
        self.uow = uow
        self.jwt_service = jwt_service
    
    async def handle(self, command: LoginCommand) -> Result[LoginResponseDTO, str]:
        """
        Execute user authentication.
        
        Args:
            command: Login command
            
        Returns:
            Result with auth tokens or error message
        """
        audit_service = None
        
        try:
            async with self.uow:
                # Parse email
                try:
                    email = Email(command.email)
                except ValueError:
                    return Failure("Invalid email format")
                
                # Find user by email
                user = await self.uow.users.get_by_email(email)
                if not user:
                    logger.warning(
                        f"Login attempt for non-existent email: {command.email}",
                        extra={"email": command.email, "ip": command.ip_address},
                    )
                    return Failure("Invalid email or password")
                
                # Set RLS context for audit logging
                self.uow.set_tenant_context(
                    organization_id=user.organization_id,
                    user_id=user.id,
                )
                
                audit_service = AuditLogService(self.uow.audit_logs)
                
                # Verify password (handles account locking)
                try:
                    user.verify_password(
                        command.password,
                        ip_address=command.ip_address,
                        user_agent=command.user_agent,
                    )
                except AccountLockedException as e:
                    # Log failed attempt
                    await audit_service.log_user_locked(
                        user_id=user.id,
                        organization_id=user.organization_id,
                        locked_until=e.unlock_at,
                        ip_address=command.ip_address,
                    )
                    await self.uow.commit()
                    
                    return Failure(str(e))
                    
                except InvalidCredentialsException:
                    # Update user with failed attempt count
                    await self.uow.users.update(user)
                    
                    # Log failed login
                    await audit_service.log_login_failed(
                        email=command.email,
                        organization_id=user.organization_id,
                        ip_address=command.ip_address,
                        user_agent=command.user_agent,
                    )
                    await self.uow.commit()
                    
                    logger.warning(
                        f"Failed login attempt: {command.email}",
                        extra={
                            "email": command.email,
                            "ip": command.ip_address,
                            "attempts": user._failed_login_attempts,
                        },
                    )
                    return Failure("Invalid email or password")
                
                # Password verified - update user
                await self.uow.users.update(user)
                self.uow.track_aggregate(user)
                
                # Get user roles
                user_roles = await self.uow.user_roles.find_by_user(user.id)
                role_ids = [ur.role_id for ur in user_roles]
                
                # Fetch role details
                roles = []
                permissions = []
                for role_id in role_ids:
                    role = await self.uow.roles.get_by_id(role_id)
                    if role:
                        roles.append(role.name)
                        permissions.extend([p.value for p in role.permissions])
                
                # Generate access token
                access_token = self.jwt_service.generate_access_token(
                    user_id=user.id,
                    organization_id=user.organization_id,
                    email=str(user.email),
                    roles=roles,
                    permissions=list(set(permissions)),  # Deduplicate
                )
                
                # Generate refresh token
                from src.identity.domain.entities.refresh_token import RefreshToken
                refresh_token_entity, plain_refresh_token = RefreshToken.create(
                    id=uuid4(),
                    user_id=user.id,
                )
                await self.uow.refresh_tokens.add(refresh_token_entity)
                
                # Log successful login
                await audit_service.log_login_success(
                    user_id=user.id,
                    organization_id=user.organization_id,
                    ip_address=command.ip_address,
                    user_agent=command.user_agent,
                )
                
                # Commit all changes
                await self.uow.commit()
                
                logger.info(
                    f"User logged in: {user.email}",
                    extra={
                        "user_id": str(user.id),
                        "organization_id": str(user.organization_id),
                        "ip": command.ip_address,
                    },
                )
                
                # Return tokens
                response = LoginResponseDTO(
                    access_token=access_token,
                    refresh_token=plain_refresh_token,
                    token_type="Bearer",
                    expires_in=JWTService.ACCESS_TOKEN_EXPIRY_MINUTES * 60,
                    user_id=str(user.id),
                    organization_id=str(user.organization_id),
                    email=str(user.email),
                    roles=roles,
                )
                
                return Success(response)
                
        except Exception as e:
            logger.error(
                f"Login failed with exception: {e}",
                extra={"command": command, "error": str(e)},
            )
            return Failure(f"Login failed: {str(e)}")
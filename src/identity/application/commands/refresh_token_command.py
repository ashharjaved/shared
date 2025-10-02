"""
Refresh Token Command
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional
from uuid import uuid4

from shared.application.base_command import BaseCommand
from shared.application.command_handler import CommandHandler
from shared.domain.result import Result, Success, Failure
from shared.infrastructure.observability.logger import get_logger

from src.identity.domain.exception import (
    RefreshTokenExpiredException,
    RefreshTokenRevokedException,
)
from src.identity.infrastructure.adapters.identity_unit_of_work import (
    IdentityUnitOfWork,
)
from src.identity.infrastructure.adapters.jwt_service import JWTService
from src.identity.infrastructure.services.audit_log_service import AuditLogService
from src.identity.application.dto.auth_dto import LoginResponseDTO

logger = get_logger(__name__)


@dataclass(frozen=True)
class RefreshTokenCommand(BaseCommand):
    """
    Command to refresh access token using refresh token.
    
    Attributes:
        refresh_token: Plain refresh token string
        ip_address: Client IP (for audit)
    """
    refresh_token: str
    ip_address: Optional[str] = None


class RefreshTokenCommandHandler(CommandHandler[RefreshTokenCommand, LoginResponseDTO]):
    """
    Handler for RefreshTokenCommand.
    
    Validates refresh token and issues new access token.
    Implements token rotation for security.
    """
    
    def __init__(
        self,
        uow: IdentityUnitOfWork,
        jwt_service: JWTService,
    ) -> None:
        self.uow = uow
        self.jwt_service = jwt_service
    
    async def handle(self, command: RefreshTokenCommand) -> Result[LoginResponseDTO, str]:
        """
        Execute token refresh.
        
        Args:
            command: Refresh token command
            
        Returns:
            Result with new tokens or error message
        """
        try:
            async with self.uow:
                # Hash the refresh token to look it up
                import hashlib
                token_hash = hashlib.sha256(command.refresh_token.encode()).hexdigest()
                
                # Find refresh token
                refresh_token = await self.uow.refresh_tokens.get_by_hash(token_hash)
                if not refresh_token:
                    logger.warning(
                        "Refresh token not found",
                        extra={"ip": command.ip_address},
                    )
                    return Failure("Invalid refresh token")
                
                # Verify token validity
                try:
                    refresh_token.verify(command.refresh_token)
                except RefreshTokenExpiredException:
                    logger.warning(
                        "Expired refresh token used",
                        extra={
                            "token_id": str(refresh_token.id),
                            "ip": command.ip_address,
                        },
                    )
                    return Failure("Refresh token has expired")
                except RefreshTokenRevokedException:
                    logger.warning(
                        "Revoked refresh token used",
                        extra={
                            "token_id": str(refresh_token.id),
                            "ip": command.ip_address,
                        },
                    )
                    return Failure("Refresh token has been revoked")
                except ValueError:
                    return Failure("Invalid refresh token")
                
                # Get user
                user = await self.uow.users.get_by_id(refresh_token.user_id)
                if not user or not user.is_active:
                    return Failure("User account is inactive")
                
                # Set RLS context
                self.uow.set_tenant_context(
                    organization_id=user.organization_id,
                    user_id=user.id,
                )
                
                # Revoke old refresh token (token rotation)
                refresh_token.revoke()
                await self.uow.refresh_tokens.update(refresh_token)
                
                # Get user roles
                user_roles = await self.uow.user_roles.find_by_user(user.id)
                role_ids = [ur.role_id for ur in user_roles]
                
                roles = []
                permissions = []
                for role_id in role_ids:
                    role = await self.uow.roles.get_by_id(role_id)
                    if role:
                        roles.append(role.name)
                        permissions.extend([p.value for p in role.permissions])
                
                # Generate new access token
                access_token = self.jwt_service.generate_access_token(
                    user_id=user.id,
                    organization_id=user.organization_id,
                    email=str(user.email),
                    roles=roles,
                    permissions=list(set(permissions)),
                )
                
                # Generate new refresh token
                from src.identity.domain.entities.refresh_token import RefreshToken
                new_refresh_token, plain_token = RefreshToken.create(
                    id=uuid4(),
                    user_id=user.id,
                )
                await self.uow.refresh_tokens.add(new_refresh_token)
                
                # Write audit log (NEW)
                audit_service = AuditLogService(self.uow.audit_logs)
                await audit_service.log(
                    action="token_refreshed",
                    organization_id=user.organization_id,
                    user_id=user.id,
                    resource_type="refresh_token",
                    resource_id=refresh_token.id,
                    metadata={
                        "old_token_id": str(refresh_token.id),
                        "new_token_id": str(new_refresh_token.id),
                        "ip_address": command.ip_address,
                    },
                )
                
                # Commit
                await self.uow.commit()
                
                logger.info(
                    "Token refreshed",
                    extra={
                        "user_id": str(user.id),
                        "organization_id": str(user.organization_id),
                        "ip": command.ip_address,
                    },
                )
                
                response = LoginResponseDTO(
                    access_token=access_token,
                    refresh_token=plain_token,
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
                f"Token refresh failed: {e}",
                extra={"error": str(e), "ip": command.ip_address},
            )
            return Failure(f"Token refresh failed: {str(e)}")
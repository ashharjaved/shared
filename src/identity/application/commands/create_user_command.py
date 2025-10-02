"""
Create User Command
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional
from uuid import UUID, uuid4

from shared.application.base_command import BaseCommand
from shared.application.command_handler import CommandHandler
from shared.domain.result import Result, Success, Failure
from shared.infrastructure.observability.logger import get_logger

from src.identity.domain.entities.user import User
from src.identity.domain.value_objects.email import Email
from src.identity.domain.value_objects.phone import Phone
from src.identity.domain.value_objects.password_hash import PasswordHash
from src.identity.domain.exception import DuplicateEmailException
from src.identity.infrastructure.adapters.identity_unit_of_work import (
    IdentityUnitOfWork,
)
from src.identity.infrastructure.services.audit_log_service import AuditLogService

logger = get_logger(__name__)


@dataclass(frozen=True)
class CreateUserCommand(BaseCommand):
    """
    Command to create a new user.
    
    Attributes:
        organization_id: Organization UUID
        email: User email address
        password: Plain text password
        full_name: User's full name
        phone: Optional phone number (E.164 format)
        created_by: User ID who created this user (for audit)
    """
    organization_id: UUID
    email: str
    password: str
    full_name: str
    phone: Optional[str] = None
    created_by: Optional[UUID] = None


class CreateUserCommandHandler(CommandHandler[CreateUserCommand, UUID]):
    """
    Handler for CreateUserCommand.
    
    Creates a new user with hashed password and raises domain events.
    """
    
    def __init__(self, uow: IdentityUnitOfWork) -> None:
        self.uow = uow
    
    async def handle(self, command: CreateUserCommand) -> Result[UUID, str]:
        """
        Execute user creation.
        
        Args:
            command: Create user command
            
        Returns:
            Result with user ID or error message
        """
        try:
            async with self.uow:
                # Set RLS context
                self.uow.set_tenant_context(
                    organization_id=command.organization_id,
                    user_id=command.created_by,
                )
                
                # Validate email format
                try:
                    email = Email(command.email)
                except ValueError as e:
                    return Failure(f"Invalid email format: {str(e)}")
                
                # Check if email already exists
                existing = await self.uow.users.get_by_email(email)
                if existing:
                    logger.warning(
                        f"Email already registered: {command.email}",
                        extra={"email": command.email},
                    )
                    return Failure(f"Email already registered: {command.email}")
                
                # Validate and parse phone if provided
                phone = None
                if command.phone:
                    try:
                        phone = Phone(command.phone)
                    except ValueError as e:
                        return Failure(f"Invalid phone format: {str(e)}")
                
                # Hash password
                try:
                    password_hash = PasswordHash.from_plain_text(command.password)
                except ValueError as e:
                    return Failure(f"Invalid password: {str(e)}")
                
                # Create user entity (raises UserCreatedEvent)
                user = User.create(
                    id=uuid4(),
                    organization_id=command.organization_id,
                    email=email,
                    password_hash=password_hash,
                    full_name=command.full_name,
                    phone=phone,
                )
                
                # Persist
                saved = await self.uow.users.add(user)
                
                # Track for domain events
                self.uow.track_aggregate(user)
                
                # Write audit log
                audit_service = AuditLogService(self.uow.audit_logs)
                await audit_service.log(
                    action="user_created",
                    organization_id=command.organization_id,
                    user_id=command.created_by,
                    resource_type="user",
                    resource_id=saved.id,
                    metadata={
                        "email": str(email),
                        "full_name": command.full_name,
                    },
                )
                
                # Commit (publishes domain events and audit log)
                await self.uow.commit()
                
                logger.info(
                    f"User created: {saved.email}",
                    extra={
                        "user_id": str(saved.id),
                        "organization_id": str(saved.organization_id),
                        "email": str(saved.email),
                    },
                )
                
                return Success(saved.id)
                
        except Exception as e:
            logger.error(
                f"Failed to create user: {e}",
                extra={"command": command, "error": str(e)},
            )
            return Failure(f"Failed to create user: {str(e)}")
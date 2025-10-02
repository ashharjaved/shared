"""
User Service
Orchestrates user-related operations
"""
from __future__ import annotations

from typing import Optional
from uuid import UUID

from shared.domain.result import Result
from shared.infrastructure.observability.logger import get_logger

from src.identity.application.commands.create_user_command import (
    CreateUserCommand,
    CreateUserCommandHandler,
)
from src.identity.application.queries.get_user_by_id_query import (
    GetUserByIdQuery,
    GetUserByIdQueryHandler,
)
from src.identity.application.queries.list_users_query import (
    ListUsersQuery,
    ListUsersQueryHandler,
)
from src.identity.application.dto.user_dto import UserDTO, UserListDTO
from src.identity.infrastructure.adapters.identity_unit_of_work import (
    IdentityUnitOfWork,
)

logger = get_logger(__name__)


class UserService:
    """
    User service for user management operations.
    
    Orchestrates commands and queries related to users.
    """
    
    def __init__(self, uow: IdentityUnitOfWork) -> None:
        self.uow = uow
    
    async def create_user(
        self,
        organization_id: UUID,
        email: str,
        password: str,
        full_name: str,
        phone: Optional[str] = None,
        created_by: Optional[UUID] = None,
    ) -> Result[UUID, str]:
        """
        Create a new user.
        
        Args:
            organization_id: Organization UUID
            email: User email
            password: Plain text password
            full_name: User's full name
            phone: Optional phone number
            created_by: User ID who created this user
            
        Returns:
            Result with user ID or error message
        """
        command = CreateUserCommand(
            organization_id=organization_id,
            email=email,
            password=password,
            full_name=full_name,
            phone=phone,
            created_by=created_by,
        )
        
        handler = CreateUserCommandHandler(self.uow)
        return await handler.handle(command)
    
    async def get_user_by_id(
        self,
        user_id: UUID,
        organization_id: UUID,
    ) -> Result[Optional[UserDTO], str]:
        """
        Get user by ID.
        
        Args:
            user_id: User UUID
            organization_id: Organization UUID (for RLS)
            
        Returns:
            Result with UserDTO or None if not found
        """
        query = GetUserByIdQuery(
            user_id=user_id,
            organization_id=organization_id,
        )
        
        handler = GetUserByIdQueryHandler(self.uow)
        return await handler.handle(query)
    
    async def list_users(
        self,
        organization_id: UUID,
        skip: int = 0,
        limit: int = 100,
        is_active: Optional[bool] = None,
    ) -> Result[UserListDTO, str]:
        """
        List users with pagination.
        
        Args:
            organization_id: Organization UUID (for RLS)
            skip: Number of records to skip
            limit: Maximum records to return
            is_active: Filter by active status
            
        Returns:
            Result with UserListDTO
        """
        query = ListUsersQuery(
            organization_id=organization_id,
            skip=skip,
            limit=limit,
            is_active=is_active,
        )
        
        handler = ListUsersQueryHandler(self.uow)
        return await handler.handle(query)
    
    async def deactivate_user(
        self,
        user_id: UUID,
        organization_id: UUID,
        deactivated_by: Optional[UUID] = None,
        reason: Optional[str] = None,
    ) -> Result[bool, str]:
        """
        Deactivate a user account.
        
        Args:
            user_id: User UUID to deactivate
            organization_id: Organization UUID (for RLS)
            deactivated_by: User ID performing deactivation
            reason: Optional deactivation reason
            
        Returns:
            Result with success boolean or error message
        """
        from src.identity.application.commands.deactivate_user_command import (
            DeactivateUserCommand,
            DeactivateUserCommandHandler,
        )
        
        command = DeactivateUserCommand(
            user_id=user_id,
            organization_id=organization_id,
            deactivated_by=deactivated_by,
            reason=reason,
        )
        
        handler = DeactivateUserCommandHandler(self.uow)
        return await handler.handle(command)
    
    async def reactivate_user(
        self,
        user_id: UUID,
        organization_id: UUID,
        reactivated_by: Optional[UUID] = None,
    ) -> Result[bool, str]:
        """
        Reactivate a user account.
        
        Args:
            user_id: User UUID to reactivate
            organization_id: Organization UUID (for RLS)
            reactivated_by: User ID performing reactivation
            
        Returns:
            Result with success boolean or error message
        """
        from src.identity.application.commands.reactivate_user_command import (
            ReactivateUserCommand,
            ReactivateUserCommandHandler,
        )
        
        command = ReactivateUserCommand(
            user_id=user_id,
            organization_id=organization_id,
            reactivated_by=reactivated_by,
        )
        
        handler = ReactivateUserCommandHandler(self.uow)
        return await handler.handle(command)
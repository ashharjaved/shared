"""
List Users Query
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional
from uuid import UUID

from shared.application.base_query import BaseQuery
from shared.application.query_handler import QueryHandler
from shared.domain.result import Result, Success, Failure
from shared.infrastructure.observability.logger import get_logger

from src.identity.infrastructure.adapters.identity_unit_of_work import (
    IdentityUnitOfWork,
)
from src.identity.application.dto.user_dto import UserDTO, UserListDTO

logger = get_logger(__name__)


@dataclass(frozen=True)
class ListUsersQuery(BaseQuery):
    """
    Query to list users with pagination.
    
    Attributes:
        organization_id: Organization UUID (for RLS)
        skip: Number of records to skip
        limit: Maximum records to return
        is_active: Filter by active status (optional)
    """
    organization_id: UUID
    skip: int = 0
    limit: int = 100
    is_active: Optional[bool] = None


class ListUsersQueryHandler(QueryHandler[ListUsersQuery, UserListDTO]):
    """
    Handler for ListUsersQuery.
    
    Retrieves paginated list of users with RLS enforcement.
    """
    
    def __init__(self, uow: IdentityUnitOfWork) -> None:
        self.uow = uow
    
    async def handle(self, query: ListUsersQuery) -> Result[UserListDTO, str]:
        """
        Execute user list query.
        
        Args:
            query: List users query
            
        Returns:
            Result with UserListDTO
        """
        try:
            async with self.uow:
                # Set RLS context
                self.uow.set_tenant_context(
                    organization_id=query.organization_id,
                )
                
                # Build filters
                filters = {}
                if query.is_active is not None:
                    filters['is_active'] = query.is_active
                
                # Get users
                users = await self.uow.users.find_all(
                    skip=query.skip,
                    limit=query.limit,
                    **filters,
                )
                
                # Map to DTOs
                user_dtos = [
                    UserDTO(
                        id=str(user.id),
                        organization_id=str(user.organization_id),
                        email=str(user.email),
                        full_name=user.full_name,
                        phone=str(user.phone) if user.phone else None,
                        is_active=user.is_active,
                        email_verified=user.email_verified,
                        phone_verified=user.phone_verified,
                        last_login_at=user.last_login_at.isoformat() if user.last_login_at else None,
                        created_at=user.created_at.isoformat(),
                    )
                    for user in users
                ]
                
                # Create list response
                list_dto = UserListDTO(
                    users=user_dtos,
                    total=len(user_dtos),
                    skip=query.skip,
                    limit=query.limit,
                )
                
                logger.debug(
                    f"Listed {len(user_dtos)} users",
                    extra={
                        "organization_id": str(query.organization_id),
                        "count": len(user_dtos),
                    },
                )
                
                return Success(list_dto)
                
        except Exception as e:
            logger.error(
                f"Failed to list users: {e}",
                extra={"query": query, "error": str(e)},
            )
            return Failure(f"Failed to list users: {str(e)}")
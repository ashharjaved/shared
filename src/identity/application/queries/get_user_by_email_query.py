"""
Get User By Email Query
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional
from uuid import UUID

from shared.application.base_query import BaseQuery
from shared.application.query_handler import QueryHandler
from shared.domain.result import Result, Success, Failure
from shared.infrastructure.observability.logger import get_logger

from src.identity.domain.value_objects.email import Email
from src.identity.infrastructure.adapters.identity_unit_of_work import (
    IdentityUnitOfWork,
)
from src.identity.application.dto.user_dto import UserDTO

logger = get_logger(__name__)


@dataclass(frozen=True)
class GetUserByEmailQuery(BaseQuery):
    """
    Query to get user by email address.
    
    Attributes:
        email: User email address
        organization_id: Organization UUID (for RLS)
    """
    email: str
    organization_id: UUID


class GetUserByEmailQueryHandler(QueryHandler[GetUserByEmailQuery, Optional[UserDTO]]):
    """
    Handler for GetUserByEmailQuery.
    
    Retrieves user by email with RLS enforcement.
    """
    
    def __init__(self, uow: IdentityUnitOfWork) -> None:
        self.uow = uow
    
    async def handle(self, query: GetUserByEmailQuery) -> Result[Optional[UserDTO], str]:
        """
        Execute user lookup by email.
        
        Args:
            query: Get user by email query
            
        Returns:
            Result with UserDTO or None if not found
        """
        try:
            async with self.uow:
                # Set RLS context
                self.uow.set_tenant_context(
                    organization_id=query.organization_id,
                )
                
                # Validate email format
                try:
                    email = Email(query.email)
                except ValueError as e:
                    return Failure(f"Invalid email format: {str(e)}")
                
                # Get user by email
                user = await self.uow.users.get_by_email(email)
                
                if not user:
                    logger.debug(
                        f"User not found by email: {query.email}",
                        extra={"email": query.email},
                    )
                    return Success(None)
                
                # Map to DTO
                user_dto = UserDTO(
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
                
                return Success(user_dto)
                
        except Exception as e:
            logger.error(
                f"Failed to get user by email: {e}",
                extra={"query": query, "error": str(e)},
            )
            return Failure(f"Failed to get user by email: {str(e)}")
"""
Get User Roles Query
"""
from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from shared.application.base_query import BaseQuery
from shared.application.query_handler import QueryHandler
from shared.domain.result import Result, Success, Failure
from shared.infrastructure.observability.logger import get_logger

from src.identity.infrastructure.adapters.identity_unit_of_work import (
    IdentityUnitOfWork,
)
from src.identity.application.dto.role_dto import RoleDTO

logger = get_logger(__name__)


@dataclass(frozen=True)
class GetUserRolesQuery(BaseQuery):
    """
    Query to get all roles assigned to a user.
    
    Attributes:
        user_id: User UUID
        organization_id: Organization UUID (for RLS)
    """
    user_id: UUID
    organization_id: UUID


class GetUserRolesQueryHandler(QueryHandler[GetUserRolesQuery, list[RoleDTO]]):
    """
    Handler for GetUserRolesQuery.
    
    Retrieves all roles for a user with their permissions.
    """
    
    def __init__(self, uow: IdentityUnitOfWork) -> None:
        self.uow = uow
    
    async def handle(self, query: GetUserRolesQuery) -> Result[list[RoleDTO], str]:
        """
        Execute user roles lookup.
        
        Args:
            query: Get user roles query
            
        Returns:
            Result with list of RoleDTOs
        """
        try:
            async with self.uow:
                # Set RLS context
                self.uow.set_tenant_context(
                    organization_id=query.organization_id,
                )
                
                # Get user-role mappings
                user_roles = await self.uow.user_roles.find_by_user(query.user_id)
                
                # Get role details
                roles = []
                for user_role in user_roles:
                    role = await self.uow.roles.get_by_id(user_role.role_id)
                    if role:
                        role_dto = RoleDTO(
                            id=str(role.id),
                            organization_id=str(role.organization_id),
                            name=role.name,
                            description=role.description,
                            permissions=[p.value for p in role.permissions],
                            is_system=role.is_system,
                            created_at=role.created_at.isoformat(),
                        )
                        roles.append(role_dto)
                
                logger.debug(
                    f"Retrieved {len(roles)} roles for user {query.user_id}",
                    extra={
                        "user_id": str(query.user_id),
                        "role_count": len(roles),
                    },
                )
                
                return Success(roles)
                
        except Exception as e:
            logger.error(
                f"Failed to get user roles: {e}",
                extra={"query": query, "error": str(e)},
            )
            return Failure(f"Failed to get user roles: {str(e)}")
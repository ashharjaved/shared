"""
Get Organization By ID Query
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
from src.identity.application.dto.organization_dto import OrganizationDTO

logger = get_logger(__name__)


@dataclass(frozen=True)
class GetOrganizationByIdQuery(BaseQuery):
    """
    Query to get organization by ID.
    
    Attributes:
        organization_id: Organization UUID
    """
    organization_id: UUID


class GetOrganizationByIdQueryHandler(QueryHandler[GetOrganizationByIdQuery, Optional[OrganizationDTO]]):
    """
    Handler for GetOrganizationByIdQuery.
    
    Retrieves organization details.
    """
    
    def __init__(self, uow: IdentityUnitOfWork) -> None:
        self.uow = uow
    
    async def handle(self, query: GetOrganizationByIdQuery) -> Result[Optional[OrganizationDTO], str]:
        """
        Execute organization lookup.
        
        Args:
            query: Get organization query
            
        Returns:
            Result with OrganizationDTO or None if not found
        """
        try:
            async with self.uow:
                # Note: Organizations don't require RLS context as they're the root tenant entity
                # But we still need a valid session
                
                # Get organization
                organization = await self.uow.organizations.get_by_id(query.organization_id)
                
                if not organization:
                    logger.debug(
                        f"Organization not found: {query.organization_id}",
                        extra={"organization_id": str(query.organization_id)},
                    )
                    return Success(None)
                
                # Map to DTO
                org_dto = OrganizationDTO(
                    id=str(organization.id),
                    name=organization.name,
                    slug=organization.slug,
                    industry=organization.industry.value,
                    is_active=organization.is_active,
                    created_at=organization.created_at.isoformat(),
                    timezone=organization.metadata.timezone if organization.metadata else "UTC",
                    language=organization.metadata.language if organization.metadata else "en",
                )
                
                return Success(org_dto)
                
        except Exception as e:
            logger.error(
                f"Failed to get organization: {e}",
                extra={"query": query, "error": str(e)},
            )
            return Failure(f"Failed to get organization: {str(e)}")
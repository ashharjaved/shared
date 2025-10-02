"""
Organization Repository Implementation
"""
from __future__ import annotations

from typing import Optional, Sequence
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from shared.infrastructure.database.sqlalchemy_repository import SQLAlchemyRepository
from src.identity.domain.entities.organization import Organization, Industry
from src.identity.domain.value_objects.organization_metadata import (
    OrganizationMetadata,
)
from src.identity.infrastructure.persistence.models.organization_model import (
    OrganizationModel,
)


class OrganizationRepository(SQLAlchemyRepository[Organization, OrganizationModel]):
    """
    Organization repository implementation.
    
    Handles persistence for Organization aggregate root.
    """
    
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(
            session=session,
            model_class=OrganizationModel,
            entity_class=Organization,
        )
    
    def _to_entity(self, model: OrganizationModel) -> Organization:
        """Convert ORM model to domain entity"""
        return Organization(
            id=model.id,
            name=model.name,
            slug=model.slug,
            industry=Industry(model.industry) if model.industry else Industry.OTHER,
            metadata=OrganizationMetadata.from_dict(model.metadata),
            is_active=model.is_active,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )
    
    def _to_model(self, entity: Organization) -> OrganizationModel:
        """Convert domain entity to ORM model"""
        return OrganizationModel(
            id=entity.id,
            name=entity.name,
            slug=entity.slug,
            industry=entity.industry.value,
            metadata=entity.metadata.to_dict(),
            is_active=entity.is_active,
            created_at=entity.created_at,
            updated_at=entity.updated_at,
        )
    
    async def get_by_slug(self, slug: str) -> Optional[Organization]:
        """
        Get organization by slug.
        
        Args:
            slug: Organization slug
            
        Returns:
            Organization if found, None otherwise
        """
        stmt = select(OrganizationModel).where(
            OrganizationModel.slug == slug,
            OrganizationModel.deleted_at.is_(None),
        )
        
        result = await self.session.execute(stmt)
        model = result.scalar_one_or_none()
        
        return self._to_entity(model) if model else None
    
    async def find_all(
        self,
        skip: int = 0,
        limit: int = 100,
        is_active: Optional[bool] = None,
    ) -> Sequence[Organization]:
        """
        Find all organizations with filters.
        
        Args:
            skip: Number of records to skip
            limit: Maximum records to return
            is_active: Filter by active status
            
        Returns:
            List of organizations
        """
        stmt = select(OrganizationModel).where(
            OrganizationModel.deleted_at.is_(None)
        )
        
        if is_active is not None:
            stmt = stmt.where(OrganizationModel.is_active == is_active)
        
        stmt = stmt.offset(skip).limit(limit).order_by(OrganizationModel.created_at.desc())
        
        result = await self.session.execute(stmt)
        models = result.scalars().all()
        
        return [self._to_entity(model) for model in models]
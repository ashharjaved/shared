# src/identity/infrastructure/repositories/tenant_repository_impl.py
"""
Tenant repository implementation.
"""

import logging
from typing import Optional, List
from uuid import UUID
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from identity.infrastructure.mapper.tenant_mapper import TenantMapper
from src.identity.domain.entities.tenant import Tenant
from src.identity.domain.repositories.tenants import TenantRepository
from src.identity.domain.types import TenantId, TenantType
from src.identity.domain.value_objects import Name, Slug, Timestamps
from src.identity.domain.errors import NotFoundInDomain, ConflictError
from src.identity.infrastructure.models.tenant_model import TenantModel
from src.shared.database.base_repository import BaseRepository
from src.shared.errors import ValidationError

logger = logging.getLogger(__name__)


class TenantRepositoryImpl(BaseRepository[TenantModel, Tenant, TenantId], TenantRepository):
    """Tenant repository implementation with RLS enforcement."""
    
    def __init__(self, session: AsyncSession):
        super().__init__(session, TenantModel, TenantMapper())
    
    async def get_by_slug(self, slug: str) -> Optional[Tenant]:
        """Retrieve tenant by unique slug."""        
        try:
            stmt = select(TenantModel).where(TenantModel.slug == slug)
            result = await self._session.execute(stmt)
            model = result.scalar_one_or_none()
            
            return self._mapper.to_domain(model) if model else None
        except Exception as e:
            logger.error("Failed to get tenant by slug", extra={"slug": slug, "error": str(e)})
            raise self._map_error(e)
    
    async def list_by_parent(self, parent_id: Optional[TenantId] = None) -> List[Tenant]:
        """List tenants by parent ID."""
        
        try:
            stmt = select(TenantModel).where(TenantModel.parent_id == parent_id)
            result = await self._session.execute(stmt)
            models = result.scalars().all()
            
            return [t for m in models if (t := self._mapper.to_domain(m)) is not None]
        except Exception as e:
            logger.error("Failed to list tenants by parent", extra={"parent_id": parent_id, "error": str(e)})
            raise self._map_error(e)
    
    async def get_hierarchy_path(self, tenant_id: TenantId) -> List[Tenant]:
        """Get full hierarchy path from root to specified tenant."""        
        try:
            # Use recursive CTE to get hierarchy path
            stmt = text("""
                WITH RECURSIVE tenant_hierarchy AS (
                    SELECT id, parent_id, name, slug, tenant_type, is_active, created_at, updated_at, 0 as level
                    FROM tenant 
                    WHERE id = :tenant_id
                    
                    UNION ALL
                    
                    SELECT t.id, t.parent_id, t.name, t.slug, t.tenant_type, t.is_active, t.created_at, t.updated_at, th.level + 1
                    FROM tenant t
                    JOIN tenant_hierarchy th ON t.id = th.parent_id
                )
                SELECT * FROM tenant_hierarchy ORDER BY level DESC
            """)
            
            result = await self._session.execute(stmt, {"tenant_id": tenant_id})
            rows = result.fetchall()
            
            if not rows:
                raise NotFoundInDomain(f"Tenant {tenant_id} not found")
            
            # Convert rows to models then to domain entities
            models = []
            for row in rows:
                model = TenantModel()
                model.id = row.id
                model.parent_id = row.parent_id
                model.name = row.name
                model.slug = row.slug
                model.tenant_type = row.tenant_type
                model.is_active = row.is_active
                model.created_at = row.created_at
                model.updated_at = row.updated_at
                models.append(model)
            
            return [t for m in models if (t := self._mapper.to_domain(m)) is not None]
        except NotFoundInDomain:
            raise
        except Exception as e:
            logger.error("Failed to get hierarchy path", extra={"tenant_id": tenant_id, "error": str(e)})
            raise self._map_error(e)
    
    async def exists_by_slug(self, slug: str, exclude_id: Optional[TenantId] = None) -> bool:
        """Check if slug is already taken."""        
        try:
            stmt = select(TenantModel.id).where(TenantModel.slug == slug)
            if exclude_id:
                stmt = stmt.where(TenantModel.id != exclude_id)
            
            result = await self._session.execute(stmt)
            return result.scalar_one_or_none() is not None
        except Exception as e:
            logger.error("Failed to check slug existence", extra={"slug": slug, "error": str(e)})
            raise self._map_error(e)
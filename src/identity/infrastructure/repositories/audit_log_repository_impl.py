# src/identity/infrastructure/repositories/audit_log_repository_impl.py
"""
Audit log repository implementation.
"""

import logging
from typing import Optional, List
from datetime import datetime, timezone
from uuid import UUID
from sqlalchemy import select, text, desc
from sqlalchemy.ext.asyncio import AsyncSession

from identity.domain.repositories.audit_logs import AuditLogsRepository
from identity.infrastructure.mapper.audit_mapper import AuditMapper
from src.identity.domain.entities.audit import AuditEntry
from src.identity.domain.types import TenantId, UserId
from src.identity.infrastructure.models.audit_log_model import AuditLogModel
from src.shared.database.base_repository import BaseRepository, Mapper

logger = logging.getLogger(__name__)


class AuditLogRepositoryImpl(BaseRepository[AuditLogModel, AuditEntry, int], AuditLogsRepository):
    """Audit log repository implementation with RLS enforcement."""
    
    def __init__(self, session: AsyncSession,):
        super().__init__(session, AuditLogModel, AuditMapper())
    
    async def create_entry(self, entry: AuditEntry) -> AuditEntry:
        """Create audit log entry."""       
        return await self.create(entry)
    
    async def list_by_resource(
        self, 
        tenant_id: TenantId,
        resource: str,
        resource_id: Optional[str] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[AuditEntry]:
        """List audit entries by resource."""
        # Set tenant context for RLS
        await self._session.execute(
            text("SELECT set_config('app.jwt_tenant', :tenant_id, true)"),
            {"tenant_id": str(tenant_id)}
        )
        
        try:
            stmt = select(AuditLogModel).where(
                AuditLogModel.actor_tenant == tenant_id,
                AuditLogModel.resource == resource
            )
            
            if resource_id:
                stmt = stmt.where(AuditLogModel.resource_id == resource_id)
            
            stmt = stmt.order_by(desc(AuditLogModel.ts)).limit(limit).offset(offset)
            
            result = await self._session.execute(stmt)
            models = result.scalars().all()
            
            return [self._mapper.to_domain(model) for model in models]
        except Exception as e:
            logger.error("Failed to list audit entries by resource", extra={"resource": resource, "error": str(e)})
            raise self._map_error(e)
    
    async def list_by_actor(
        self,
        tenant_id: TenantId,
        actor_id: UserId,
        limit: int = 100,
        offset: int = 0
    ) -> List[AuditEntry]:
        """List audit entries by actor."""
        # Set tenant context for RLS
        await self._session.execute(
            text("SELECT set_config('app.jwt_tenant', :tenant_id, true)"),
            {"tenant_id": str(tenant_id)}
        )
        
        try:
            stmt = select(AuditLogModel).where(
                AuditLogModel.actor_tenant == tenant_id,
                AuditLogModel.actor_user == actor_id
            ).order_by(desc(AuditLogModel.ts)).limit(limit).offset(offset)
            
            result = await self._session.execute(stmt)
            models = result.scalars().all()
            
            return [self._mapper.to_domain(model) for model in models]
        except Exception as e:
            logger.error("Failed to list audit entries by actor", extra={"actor_id": actor_id, "error": str(e)})
            raise self._map_error(e)
    
    async def list_by_tenant(
        self,
        tenant_id: TenantId,
        since: Optional[datetime] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[AuditEntry]:
        """List audit entries for tenant."""
        # Set tenant context for RLS
        await self._session.execute(
            text("SELECT set_config('app.jwt_tenant', :tenant_id, true)"),
            {"tenant_id": str(tenant_id)}
        )
        
        try:
            stmt = select(AuditLogModel).where(AuditLogModel.actor_tenant == tenant_id)
            
            if since:
                stmt = stmt.where(AuditLogModel.ts >= since)
            
            stmt = stmt.order_by(desc(AuditLogModel.ts)).limit(limit).offset(offset)
            
            result = await self._session.execute(stmt)
            models = result.scalars().all()
            
            return [self._mapper.to_domain(model) for model in models]
        except Exception as e:
            logger.error("Failed to list audit entries by tenant", extra={"tenant_id": tenant_id, "error": str(e)})
            raise self._map_error(e)
"""
AuditLog Repository Implementation
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional, Sequence
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from shared.infrastructure.database.sqlalchemy_repository import SQLAlchemyRepository
from src.identity.domain.entities.audit_log import AuditLog
from src.identity.infrastructure.persistence.models.audit_log_model import (
    AuditLogModel,
)


class AuditLogRepository(SQLAlchemyRepository[AuditLog, AuditLogModel]):
    """
    AuditLog repository implementation.
    
    Immutable append-only audit trail.
    """
    
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(
            session=session,
            model_class=AuditLogModel,
            entity_class=AuditLog,
        )
    
    def _to_entity(self, model: AuditLogModel) -> AuditLog:
        """Convert ORM model to domain entity"""
        return AuditLog(
            id=model.id,
            organization_id=model.organization_id,
            user_id=model.user_id,
            action=model.action,
            resource_type=model.resource_type,
            resource_id=model.resource_id,
            ip_address=str(model.ip_address) if model.ip_address else None,
            user_agent=model.user_agent,
            metadata=model.metadata,
            created_at=model.created_at,
        )
    
    def _to_model(self, entity: AuditLog) -> AuditLogModel:
        """Convert domain entity to ORM model"""
        return AuditLogModel(
            id=entity.id,
            organization_id=entity.organization_id,
            user_id=entity.user_id,
            action=entity.action,
            resource_type=entity.resource_type,
            resource_id=entity.resource_id,
            ip_address=entity.ip_address,
            user_agent=entity.user_agent,
            metadata=entity.metadata,
            created_at=entity.created_at,
        )
    
    async def find_by_organization(
        self,
        organization_id: UUID,
        skip: int = 0,
        limit: int = 100,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        action: Optional[str] = None,
    ) -> Sequence[AuditLog]:
        """
        Find audit logs for an organization with filters.
        
        Args:
            organization_id: Organization UUID
            skip: Number of records to skip
            limit: Maximum records to return
            start_date: Filter logs after this date
            end_date: Filter logs before this date
            action: Filter by action type
            
        Returns:
            List of audit logs
        """
        stmt = select(AuditLogModel).where(
            AuditLogModel.organization_id == organization_id
        )
        
        if start_date:
            stmt = stmt.where(AuditLogModel.created_at >= start_date)
        if end_date:
            stmt = stmt.where(AuditLogModel.created_at <= end_date)
        if action:
            stmt = stmt.where(AuditLogModel.action == action)
        
        stmt = stmt.offset(skip).limit(limit).order_by(AuditLogModel.created_at.desc())
        
        result = await self.session.execute(stmt)
        models = result.scalars().all()
        
        return [self._to_entity(model) for model in models]
    
    async def find_by_user(
        self,
        user_id: UUID,
        skip: int = 0,
        limit: int = 100,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> Sequence[AuditLog]:
        """
        Find audit logs for a user.
        
        Args:
            user_id: User UUID
            skip: Number of records to skip
            limit: Maximum records to return
            start_date: Filter logs after this date
            end_date: Filter logs before this date
            
        Returns:
            List of audit logs
        """
        stmt = select(AuditLogModel).where(AuditLogModel.user_id == user_id)
        
        if start_date:
            stmt = stmt.where(AuditLogModel.created_at >= start_date)
        if end_date:
            stmt = stmt.where(AuditLogModel.created_at <= end_date)
        
        stmt = stmt.offset(skip).limit(limit).order_by(AuditLogModel.created_at.desc())
        
        result = await self.session.execute(stmt)
        models = result.scalars().all()
        
        return [self._to_entity(model) for model in models]
    
    async def find_by_resource(
        self,
        resource_type: str,
        resource_id: UUID,
        skip: int = 0,
        limit: int = 100,
    ) -> Sequence[AuditLog]:
        """
        Find audit logs for a specific resource.
        
        Args:
            resource_type: Resource type (e.g., 'user', 'role')
            resource_id: Resource UUID
            skip: Number of records to skip
            limit: Maximum records to return
            
        Returns:
            List of audit logs
        """
        stmt = (
            select(AuditLogModel)
            .where(
                AuditLogModel.resource_type == resource_type,
                AuditLogModel.resource_id == resource_id,
            )
            .offset(skip)
            .limit(limit)
            .order_by(AuditLogModel.created_at.desc())
        )
        
        result = await self.session.execute(stmt)
        models = result.scalars().all()
        
        return [self._to_entity(model) for model in models]
    
    async def count_by_organization(
        self,
        organization_id: UUID,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> int:
        """
        Count audit logs for an organization.
        
        Args:
            organization_id: Organization UUID
            start_date: Filter logs after this date
            end_date: Filter logs before this date
            
        Returns:
            Count of audit logs
        """
        stmt = select(func.count()).select_from(AuditLogModel).where(
            AuditLogModel.organization_id == organization_id
        )
        
        if start_date:
            stmt = stmt.where(AuditLogModel.created_at >= start_date)
        if end_date:
            stmt = stmt.where(AuditLogModel.created_at <= end_date)
        
        result = await self.session.execute(stmt)
        return result.scalar_one()
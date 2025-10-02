"""
AuditLog Repository Protocol (Interface)
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional, Protocol, Sequence
from uuid import UUID

from src.identity.domain.entities.audit_log import AuditLog


class IAuditLogRepository(Protocol):
    """Audit log repository interface"""
    
    async def add(self, log: AuditLog) -> AuditLog:
        """Add new audit log entry"""
        ...
    
    async def get_by_id(self, log_id: UUID) -> Optional[AuditLog]:
        """Get log entry by ID"""
        ...
    
    async def find_by_organization(
        self,
        organization_id: UUID,
        skip: int = 0,
        limit: int = 100,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        action: Optional[str] = None,
    ) -> Sequence[AuditLog]:
        """Find audit logs for an organization with filters"""
        ...
    
    async def find_by_user(
        self,
        user_id: UUID,
        skip: int = 0,
        limit: int = 100,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> Sequence[AuditLog]:
        """Find audit logs for a user"""
        ...
    
    async def find_by_resource(
        self,
        resource_type: str,
        resource_id: UUID,
        skip: int = 0,
        limit: int = 100,
    ) -> Sequence[AuditLog]:
        """Find audit logs for a specific resource"""
        ...
    
    async def count_by_organization(
        self,
        organization_id: UUID,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> int:
        """Count audit logs for an organization"""
        ...
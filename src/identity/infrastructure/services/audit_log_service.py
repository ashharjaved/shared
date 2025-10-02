"""
Audit Log Service - Infrastructure
Handles audit log writing with automatic context capture
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Optional
from uuid import UUID, uuid4

from shared.infrastructure.observability.logger import get_logger
from src.identity.domain.entities.audit_log import AuditLog, AuditAction
from src.identity.domain.protocols.audit_log_repository_protocol import (
    IAuditLogRepository,
)

logger = get_logger(__name__)


class AuditLogService:
    """
    Infrastructure service for writing audit logs.
    
    Captures context automatically and writes immutable audit trail.
    Used by application services to record security events.
    """
    
    def __init__(self, audit_log_repository: IAuditLogRepository) -> None:
        self._repository = audit_log_repository
    
    async def log(
        self,
        action: str,
        organization_id: Optional[UUID] = None,
        user_id: Optional[UUID] = None,
        resource_type: Optional[str] = None,
        resource_id: Optional[UUID] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> AuditLog:
        """
        Write an audit log entry.
        
        Args:
            action: Action identifier (use AuditAction constants)
            organization_id: Organization UUID
            user_id: User who performed the action
            resource_type: Type of resource affected
            resource_id: UUID of affected resource
            ip_address: Client IP address
            user_agent: Client user agent
            metadata: Additional context
            
        Returns:
            Created AuditLog entity
        """
        audit_log = AuditLog.create(
            id=uuid4(),
            action=action,
            organization_id=organization_id,
            user_id=user_id,
            resource_type=resource_type,
            resource_id=resource_id,
            ip_address=ip_address,
            user_agent=user_agent,
            metadata=metadata or {},
        )
        
        # Write to repository (immutable)
        saved_log = await self._repository.add(audit_log)
        
        # Also log to structured logs for observability
        logger.info(
            f"Audit: {action}",
            extra={
                "audit_id": str(saved_log.id),
                "organization_id": str(organization_id) if organization_id else None,
                "user_id": str(user_id) if user_id else None,
                "action": action,
                "resource_type": resource_type,
                "resource_id": str(resource_id) if resource_id else None,
                "ip_address": ip_address,
            },
        )
        
        return saved_log
    
    async def log_login_success(
        self,
        user_id: UUID,
        organization_id: UUID,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> AuditLog:
        """Log successful login"""
        return await self.log(
            action=AuditAction.LOGIN_SUCCESS,
            organization_id=organization_id,
            user_id=user_id,
            resource_type="user",
            resource_id=user_id,
            ip_address=ip_address,
            user_agent=user_agent,
        )
    
    async def log_login_failed(
        self,
        email: str,
        organization_id: Optional[UUID] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        reason: str = "invalid_credentials",
    ) -> AuditLog:
        """Log failed login attempt"""
        return await self.log(
            action=AuditAction.LOGIN_FAILED,
            organization_id=organization_id,
            ip_address=ip_address,
            user_agent=user_agent,
            metadata={
                "email": email,
                "reason": reason,
            },
        )
    
    async def log_role_assigned(
        self,
        user_id: UUID,
        role_id: UUID,
        organization_id: UUID,
        role_name: str,
        assigned_by: Optional[UUID] = None,
    ) -> AuditLog:
        """Log role assignment"""
        return await self.log(
            action=AuditAction.ROLE_ASSIGNED,
            organization_id=organization_id,
            user_id=assigned_by,
            resource_type="user",
            resource_id=user_id,
            metadata={
                "role_id": str(role_id),
                "role_name": role_name,
                "target_user_id": str(user_id),
            },
        )
    
    async def log_role_revoked(
        self,
        user_id: UUID,
        role_id: UUID,
        organization_id: UUID,
        role_name: str,
        revoked_by: Optional[UUID] = None,
    ) -> AuditLog:
        """Log role revocation"""
        return await self.log(
            action=AuditAction.ROLE_REVOKED,
            organization_id=organization_id,
            user_id=revoked_by,
            resource_type="user",
            resource_id=user_id,
            metadata={
                "role_id": str(role_id),
                "role_name": role_name,
                "target_user_id": str(user_id),
            },
        )
    
    async def log_password_changed(
        self,
        user_id: UUID,
        organization_id: UUID,
        changed_by: Optional[UUID] = None,
        ip_address: Optional[str] = None,
    ) -> AuditLog:
        """Log password change"""
        return await self.log(
            action=AuditAction.PASSWORD_CHANGED,
            organization_id=organization_id,
            user_id=changed_by or user_id,
            resource_type="user",
            resource_id=user_id,
            ip_address=ip_address,
            metadata={
                "self_service": changed_by is None or changed_by == user_id,
            },
        )
    
    async def log_user_locked(
        self,
        user_id: UUID,
        organization_id: UUID,
        locked_until: datetime,
        ip_address: Optional[str] = None,
    ) -> AuditLog:
        """Log account lock"""
        return await self.log(
            action=AuditAction.USER_LOCKED,
            organization_id=organization_id,
            resource_type="user",
            resource_id=user_id,
            ip_address=ip_address,
            metadata={
                "locked_until": locked_until.isoformat(),
                "reason": "excessive_failed_attempts",
            },
        )
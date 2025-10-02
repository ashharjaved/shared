"""
AuditLog Entity - Security and Compliance Audit Trail
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional, Dict, Any
from uuid import UUID

from shared.domain.base_entity import BaseEntity


class AuditAction:
    """Enumeration of auditable actions"""
    
    # Authentication
    LOGIN_SUCCESS = "login_success"
    LOGIN_FAILED = "login_failed"
    LOGOUT = "logout"
    PASSWORD_CHANGED = "password_changed"
    PASSWORD_RESET_REQUESTED = "password_reset_requested"
    PASSWORD_RESET_COMPLETED = "password_reset_completed"
    
    # Account Management
    USER_CREATED = "user_created"
    USER_UPDATED = "user_updated"
    USER_DELETED = "user_deleted"
    USER_ACTIVATED = "user_activated"
    USER_DEACTIVATED = "user_deactivated"
    USER_LOCKED = "user_locked"
    USER_UNLOCKED = "user_unlocked"
    
    # RBAC
    ROLE_ASSIGNED = "role_assigned"
    ROLE_REVOKED = "role_revoked"
    PERMISSION_GRANTED = "permission_granted"
    PERMISSION_REVOKED = "permission_revoked"
    ROLE_CREATED = "role_created"
    ROLE_UPDATED = "role_updated"
    ROLE_DELETED = "role_deleted"
    
    # Organization
    ORGANIZATION_CREATED = "organization_created"
    ORGANIZATION_UPDATED = "organization_updated"
    ORGANIZATION_DELETED = "organization_deleted"
    
    # Access Control
    UNAUTHORIZED_ACCESS = "unauthorized_access"
    FORBIDDEN_ACCESS = "forbidden_access"
    
    # API Keys
    API_KEY_CREATED = "api_key_created"
    API_KEY_REVOKED = "api_key_revoked"
    API_KEY_USED = "api_key_used"


class AuditLog(BaseEntity):
    """
    Audit log entity for security and compliance tracking.
    
    Records all security-critical events with full context for:
    - Regulatory compliance (GDPR, HIPAA)
    - Security incident investigation
    - User activity monitoring
    - Forensic analysis
    
    Retention: 7 years minimum per compliance requirements
    
    Attributes:
        organization_id: Organization UUID (nullable for platform events)
        user_id: User who performed the action (nullable for system events)
        action: Action identifier (from AuditAction)
        resource_type: Type of resource affected (e.g., 'user', 'role')
        resource_id: UUID of the affected resource
        ip_address: Client IP address
        user_agent: Client user agent string
        metadata: Additional context (JSON)
    """
    
    def __init__(
        self,
        id: UUID,
        organization_id: Optional[UUID],
        user_id: Optional[UUID],
        action: str,
        resource_type: Optional[str] = None,
        resource_id: Optional[UUID] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        created_at: Optional[datetime] = None,
        updated_at: Optional[datetime] = None,
        deleted_at: Optional[datetime] = None,
    ) -> None:
        super().__init__(id, created_at, updated_at)
        self._organization_id = organization_id
        self._user_id = user_id
        self._action = action
        self._resource_type = resource_type
        self._resource_id = resource_id
        self._ip_address = ip_address
        self._user_agent = user_agent
        self._metadata = metadata or {}
    
    @staticmethod
    def create(
        id: UUID,
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
        Factory method to create an audit log entry.
        
        Args:
            id: Log entry UUID
            action: Action identifier (use AuditAction constants)
            organization_id: Organization UUID
            user_id: User UUID
            resource_type: Resource type (e.g., 'user', 'role')
            resource_id: Resource UUID
            ip_address: Client IP
            user_agent: Client user agent
            metadata: Additional context
            
        Returns:
            New AuditLog instance
        """
        return AuditLog(
            id=id,
            organization_id=organization_id,
            user_id=user_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            ip_address=ip_address,
            user_agent=user_agent,
            metadata=metadata or {},
        )
    
    # Properties
    @property
    def organization_id(self) -> Optional[UUID]:
        return self._organization_id
    
    @property
    def user_id(self) -> Optional[UUID]:
        return self._user_id
    
    @property
    def action(self) -> str:
        return self._action
    
    @property
    def resource_type(self) -> Optional[str]:
        return self._resource_type
    
    @property
    def resource_id(self) -> Optional[UUID]:
        return self._resource_id
    
    @property
    def ip_address(self) -> Optional[str]:
        return self._ip_address
    
    @property
    def user_agent(self) -> Optional[str]:
        return self._user_agent
    
    @property
    def metadata(self) -> Dict[str, Any]:
        return self._metadata.copy()  # Return copy to prevent mutation
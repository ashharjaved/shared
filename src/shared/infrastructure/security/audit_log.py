"""
Audit Logging for Security-Critical Operations
Centralized audit trail for compliance
"""
from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from shared.infrastructure.observability.logger import get_logger

logger = get_logger(__name__)


class AuditLogger:
    """
    Centralized audit logger for security and compliance.
    
    Logs all security-critical operations:
    - Authentication (login, logout, password change)
    - Authorization (permission grants/revokes)
    - Data access (sensitive data reads)
    - Configuration changes
    
    Audit logs should be:
    - Immutable (append-only)
    - Tamper-evident
    - Retained per compliance requirements
    """
    
    @staticmethod
    def log_auth_event(
        event_type: str,
        user_id: UUID | None,
        organization_id: UUID | None,
        success: bool,
        ip_address: str | None = None,
        user_agent: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """
        Log an authentication/authorization event.
        
        Args:
            event_type: Type of event (login, logout, permission_grant, etc.)
            user_id: User UUID (if authenticated)
            organization_id: Organization UUID
            success: Whether operation succeeded
            ip_address: Client IP address
            user_agent: Client user agent
            metadata: Additional event metadata
        """
        log_entry = {
            "event_category": "authentication",
            "event_type": event_type,
            "user_id": str(user_id) if user_id else None,
            "organization_id": str(organization_id) if organization_id else None,
            "success": success,
            "ip_address": ip_address,
            "user_agent": user_agent,
            "timestamp": datetime.utcnow().isoformat(),
            "metadata": metadata or {},
        }
        
        # Log at appropriate level
        if success:
            logger.info(
                f"Auth event: {event_type}",
                extra=log_entry,
            )
        else:
            logger.warning(
                f"Auth event failed: {event_type}",
                extra=log_entry,
            )
    
    @staticmethod
    def log_data_access(
        resource_type: str,
        resource_id: UUID,
        action: str,
        user_id: UUID,
        organization_id: UUID,
        sensitive: bool = False,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """
        Log data access event (especially for sensitive data).
        
        Args:
            resource_type: Type of resource (user, conversation, etc.)
            resource_id: Resource UUID
            action: Action performed (read, update, delete)
            user_id: User performing action
            organization_id: Organization context
            sensitive: Whether data is sensitive (PII, PHI, etc.)
            metadata: Additional metadata
        """
        log_entry = {
            "event_category": "data_access",
            "resource_type": resource_type,
            "resource_id": str(resource_id),
            "action": action,
            "user_id": str(user_id),
            "organization_id": str(organization_id),
            "sensitive": sensitive,
            "timestamp": datetime.utcnow().isoformat(),
            "metadata": metadata or {},
        }
        
        if sensitive:
            logger.warning(
                f"Sensitive data accessed: {resource_type}",
                extra=log_entry,
            )
        else:
            logger.info(
                f"Data accessed: {resource_type}",
                extra=log_entry,
            )
    
    @staticmethod
    def log_config_change(
        config_type: str,
        config_id: UUID | None,
        change_type: str,
        user_id: UUID,
        organization_id: UUID,
        old_value: Any = None,
        new_value: Any = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """
        Log configuration change event.
        
        Args:
            config_type: Type of configuration (role, permission, etc.)
            config_id: Configuration UUID
            change_type: Type of change (create, update, delete)
            user_id: User making change
            organization_id: Organization context
            old_value: Previous value (for updates)
            new_value: New value
            metadata: Additional metadata
        """
        log_entry = {
            "event_category": "configuration",
            "config_type": config_type,
            "config_id": str(config_id) if config_id else None,
            "change_type": change_type,
            "user_id": str(user_id),
            "organization_id": str(organization_id),
            "old_value": old_value,
            "new_value": new_value,
            "timestamp": datetime.utcnow().isoformat(),
            "metadata": metadata or {},
        }
        
        logger.info(
            f"Config changed: {config_type}",
            extra=log_entry,
        )
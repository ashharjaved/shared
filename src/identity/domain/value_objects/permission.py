"""
Permission Value Object
"""
from __future__ import annotations

import re
from typing import Final

from shared.domain.base_value_object import BaseValueObject


# Permission format: resource:action (e.g., 'chatbot:read', 'campaign:write')
PERMISSION_REGEX: Final[str] = r'^[a-z_]+:[a-z_]+$'


class Permission(BaseValueObject):
    """
    Permission value object for RBAC.
    
    Format: 'resource:action'
    Examples:
        - chatbot:read
        - chatbot:write
        - campaign:read
        - campaign:write
        - user:manage
        - analytics:view
    
    Permissions are immutable strings with validation.
    """
    
    # Common permissions
    CHATBOT_READ = "chatbot:read"
    CHATBOT_WRITE = "chatbot:write"
    CAMPAIGN_READ = "campaign:read"
    CAMPAIGN_WRITE = "campaign:write"
    CAMPAIGN_SEND = "campaign:send"
    USER_READ = "user:read"
    USER_WRITE = "user:write"
    USER_MANAGE = "user:manage"
    ROLE_READ = "role:read"
    ROLE_WRITE = "role:write"
    ANALYTICS_VIEW = "analytics:view"
    ANALYTICS_EXPORT = "analytics:export"
    ORGANIZATION_READ = "organization:read"
    ORGANIZATION_WRITE = "organization:write"
    ORGANIZATION_MANAGE = "organization:manage"
    SYSTEM_CONFIG = "system:config"
    
    def __init__(self, value: str) -> None:
        normalized = value.lower().strip()
        
        if not re.match(PERMISSION_REGEX, normalized):
            raise ValueError(
                f"Invalid permission format: {value}. Must be 'resource:action' (lowercase, underscores allowed)"
            )
        
        self._value = normalized
        self._finalize_init()
    
    @property
    def value(self) -> str:
        return self._value
    
    @property
    def resource(self) -> str:
        """Extract resource part (before colon)"""
        return self._value.split(":")[0]
    
    @property
    def action(self) -> str:
        """Extract action part (after colon)"""
        return self._value.split(":")[1]
    
    def __str__(self) -> str:
        return self._value
    
    def _get_equality_components(self) -> tuple:
        return (self._value,)
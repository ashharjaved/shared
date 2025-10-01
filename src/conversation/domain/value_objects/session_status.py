# src/conversation/domain/value_objects/session_status.py
"""Session status value object."""

from enum import Enum


class SessionStatus(str, Enum):
    """Session lifecycle status."""
    
    ACTIVE = "active"
    COMPLETED = "completed"
    EXPIRED = "expired"
    ABANDONED = "abandoned"
    
    def __str__(self) -> str:
        return self.value
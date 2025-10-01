# src/conversation/domain/value_objects/flow_status.py
"""Flow status value object."""

from enum import Enum


class FlowStatus(str, Enum):
    """Flow lifecycle status."""
    
    DRAFT = "draft"
    PUBLISHED = "published"
    ARCHIVED = "archived"
    
    def __str__(self) -> str:
        return self.value
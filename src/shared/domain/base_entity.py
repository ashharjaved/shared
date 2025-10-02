"""
Base Entity Contract for Domain Layer
Provides UUID-based identity, equality, and audit fields
"""
from __future__ import annotations

from abc import ABC
from datetime import datetime
from uuid import UUID, uuid4


class BaseEntity(ABC):
    """
    Abstract base class for all domain entities.
    
    Entities are defined by their identity (id), not their attributes.
    Two entities are equal if they have the same id, regardless of other attributes.
    
    Attributes:
        id: Unique identifier (UUID)
        created_at: Timestamp of creation
        updated_at: Timestamp of last update
    """
    
    def __init__(
        self,
        id: UUID | None = None,
        created_at: datetime | None = None,
        updated_at: datetime | None = None,
    ) -> None:
        """
        Initialize entity with identity and audit fields.
        
        Args:
            id: Entity UUID (generated if None)
            created_at: Creation timestamp (now if None)
            updated_at: Update timestamp (now if None)
        """
        self.id: UUID = id or uuid4()
        self.created_at: datetime = created_at or datetime.utcnow()
        self.updated_at: datetime = updated_at or datetime.utcnow()
    
    def __eq__(self, other: object) -> bool:
        """Entities are equal if they have the same id and type."""
        if not isinstance(other, self.__class__):
            return False
        return self.id == other.id
    
    def __hash__(self) -> int:
        """Hash based on id for use in sets/dicts."""
        return hash(self.id)
    
    def __repr__(self) -> str:
        """String representation showing class name and id."""
        return f"{self.__class__.__name__}(id={self.id})"
    
    def mark_updated(self) -> None:
        """Update the updated_at timestamp to current time."""
        self.updated_at = datetime.utcnow()
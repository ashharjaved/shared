"""
Base Query Contract for CQRS
All queries (read operations) inherit from this
"""
from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class BaseQuery:
    """
    Base class for all queries in the system.
    
    Queries represent read operations and should not modify state.
    They are immutable data structures that carry query parameters.
    
    Each query should have a corresponding QueryHandler.
    
    Example:
        @dataclass(frozen=True)
        class GetUserByIdQuery(BaseQuery):
            user_id: UUID
            organization_id: UUID
    """
    
    # Optional: query metadata
    query_id: UUID | None = None
    requested_by: UUID | None = None  # User who requested the query
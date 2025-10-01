# src/conversation/domain/repositories/flow_repository.py
"""Flow repository protocol."""

from abc import ABC, abstractmethod
from typing import Optional, List
from uuid import UUID

from src.conversation.domain.entities.flow import Flow


class FlowRepository(ABC):
    """Protocol for flow persistence."""
    
    @abstractmethod
    async def add(self, flow: Flow) -> None:
        """Add new flow."""
        pass
    
    @abstractmethod
    async def get_by_id(self, flow_id: UUID, tenant_id: UUID) -> Optional[Flow]:
        """Get flow by ID with RLS."""
        pass
    
    @abstractmethod
    async def get_published_flows(self, tenant_id: UUID, language: Optional[str] = None) -> List[Flow]:
        """Get all published flows for tenant."""
        pass
    
    @abstractmethod
    async def update(self, flow: Flow) -> None:
        """Update existing flow."""
        pass
    
    @abstractmethod
    async def delete(self, flow_id: UUID, tenant_id: UUID) -> None:
        """Soft delete flow (archive)."""
        pass
    
    @abstractmethod
    async def find_by_name(self, tenant_id: UUID, name: str) -> Optional[Flow]:
        """Find flow by name."""
        pass
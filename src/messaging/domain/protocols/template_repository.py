"""
Template Repository Protocol
Defines persistence interface for MessageTemplate.
"""
from abc import abstractmethod
from typing import Optional, List, Protocol
from uuid import UUID

from src.messaging.domain.entities.message_template import MessageTemplate


class TemplateRepository(Protocol):
    """Repository protocol for MessageTemplate."""
    
    @abstractmethod
    async def get_by_id(self, template_id: UUID) -> Optional[MessageTemplate]:
        """Retrieve template by ID."""
        ...
    
    @abstractmethod
    async def get_by_name_and_language(
        self, tenant_id: UUID, name: str, language: str
    ) -> Optional[MessageTemplate]:
        """Find template by name and language."""
        ...
    
    @abstractmethod
    async def list_by_tenant(
        self, tenant_id: UUID, status: Optional[str] = None
    ) -> List[MessageTemplate]:
        """List templates for a tenant, optionally filtered by status."""
        ...
    
    @abstractmethod
    async def create(self, template: MessageTemplate) -> MessageTemplate:
        """Persist new template."""
        ...
    
    @abstractmethod
    async def update(self, template: MessageTemplate) -> MessageTemplate:
        """Update existing template."""
        ...
"""
Organization Domain Events
"""
from __future__ import annotations

from datetime import datetime
from uuid import UUID

from shared.domain.domain_event import DomainEvent


class OrganizationCreatedEvent(DomainEvent):
    """Raised when a new organization is created"""
    
    def __init__(
        self,
        organization_id: UUID,
        name: str,
        slug: str,
        industry: str,
        occurred_at: datetime | None = None,
    ) -> None:
        if occurred_at is not None:
            super().__init__(occurred_at=occurred_at)
        else:
            super().__init__()
        self.organization_id = organization_id
        self.name = name
        self.slug = slug
        self.industry = industry


class OrganizationActivatedEvent(DomainEvent):
    """Raised when an organization is activated"""
    
    def __init__(
        self,
        organization_id: UUID,
        name: str,
        occurred_at: datetime | None = None,
    ) -> None:
        if occurred_at is not None:
            super().__init__(occurred_at=occurred_at)
        else:
            super().__init__()
        self.organization_id = organization_id
        self.name = name


class OrganizationDeactivatedEvent(DomainEvent):
    """Raised when an organization is deactivated"""
    
    def __init__(
        self,
        organization_id: UUID,
        name: str,
        occurred_at: datetime | None = None,
    ) -> None:
        if occurred_at is not None:
            super().__init__(occurred_at=occurred_at)
        else:
            super().__init__()
        self.organization_id = organization_id
        self.name = name
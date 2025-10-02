"""
Organization Entity - Multi-tenant root
Represents the top-level tenant in the hierarchy
"""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional
from uuid import UUID

from shared.domain.base_aggregate_root import BaseAggregateRoot
from src.identity.domain.value_objects.organization_metadata import OrganizationMetadata
from src.identity.domain.events.organization_events import (
    OrganizationCreatedEvent,
    OrganizationActivatedEvent,
    OrganizationDeactivatedEvent,
)


class Industry(str, Enum):
    """Industry vertical types"""
    HEALTHCARE = "healthcare"
    EDUCATION = "education"
    RETAIL = "retail"
    FINANCE = "finance"
    OTHER = "other"


class Organization(BaseAggregateRoot):
    """
    Organization aggregate root.
    
    Represents the top-level tenant with complete data isolation.
    All users, conversations, and resources belong to an organization.
    
    Attributes:
        name: Organization display name
        slug: URL-safe unique identifier
        industry: Business vertical
        metadata: Additional configuration (JSONB)
        is_active: Whether organization can access the platform
    """
    
    def __init__(
        self,
        id: UUID,
        name: str,
        slug: str,
        industry: Industry,
        metadata: OrganizationMetadata,
        is_active: bool = True,
        created_at: Optional[datetime] = None,
        updated_at: Optional[datetime] = None,
        deleted_at: Optional[datetime] = None,
    ) -> None:
        super().__init__(id, created_at=created_at, updated_at= updated_at, deleted_at=deleted_at)
        self._name = name
        self._slug = slug
        self._industry = industry
        self._metadata = metadata
        self._is_active = is_active

    @staticmethod
    def create(
        id: UUID,
        name: str,
        slug: str,
        industry: Industry,
        metadata: OrganizationMetadata,
    ) -> Organization:
        """
        Factory method to create a new organization.
        
        Args:
            id: Unique identifier (UUID)
            name: Organization name
            slug: URL-safe slug
            industry: Business vertical
            metadata: Configuration metadata
            
        Returns:
            New Organization instance with CreatedEvent raised
        """
        org = Organization(
            id=id,
            name=name,
            slug=slug,
            industry=industry,
            metadata=metadata,
            is_active=True,
        )
        
        org.raise_event(
            OrganizationCreatedEvent(
                organization_id=id,
                name=name,
                slug=slug,
                industry=industry.value,
            )
        )
        
        return org
    
    def activate(self) -> None:
        """Activate organization (allow access)"""
        if self._is_active:
            return
        
        self._is_active = True
        self._touch()
        
        self.raise_event(
            OrganizationActivatedEvent(
                organization_id=self.id,
                name=self._name,
            )
        )
    
    def deactivate(self) -> None:
        """Deactivate organization (block access)"""
        if not self._is_active:
            return
        
        self._is_active = False
        self._touch()
        
        self.raise_event(
            OrganizationDeactivatedEvent(
                organization_id=self.id,
                name=self._name,
            )
        )
    
    def update_metadata(self, metadata: OrganizationMetadata) -> None:
        """Update organization configuration"""
        self._metadata = metadata
        self._touch()
    
    # Properties
    @property
    def name(self) -> str:
        return self._name
    
    @property
    def slug(self) -> str:
        return self._slug
    
    @property
    def industry(self) -> Industry:
        return self._industry
    
    @property
    def metadata(self) -> OrganizationMetadata:
        return self._metadata
    
    @property
    def is_active(self) -> bool:
        return self._is_active
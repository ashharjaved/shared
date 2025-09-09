# src/identity/domain/events/tenant_events.py
"""
Domain events related to tenant lifecycle and management.

All events are immutable and contain complete data needed by downstream systems.
"""

from dataclasses import Field, dataclass
from datetime import datetime
from typing import Optional, Dict, Any
from uuid import UUID, uuid4

from identity.domain.events._base import EventBase

from ..types import PlanId, TenantId, UserId


@dataclass(frozen=True, slots=True)
class TenantCreated:
    """
    Event fired when a new tenant is created.
    
    Contains full tenant data for downstream processing like 
    setting up default configurations, sending welcome emails, etc.
    """
    
    id: UUID
    occurred_at: datetime
    tenant_id: TenantId
    name: str
    slug: str
    tenant_type: str
    parent_tenant_id: Optional[TenantId]
    created_by_user_id: Optional[UUID]
    
    def __post_init__(self) -> None:
        """Validate event data."""
        if not self.name.strip():
            raise ValueError("Tenant name cannot be empty")
        if not self.slug.strip():
            raise ValueError("Tenant slug cannot be empty")
        if not self.tenant_type.strip():
            raise ValueError("Tenant type cannot be empty")
    
    def as_dict(self) -> Dict[str, Any]:
        """Convert event to dictionary for serialization."""
        return {
            "id": str(self.id),
            "occurred_at": self.occurred_at.isoformat(),
            "tenant_id": str(self.tenant_id),
            "name": self.name,
            "slug": self.slug,
            "tenant_type": self.tenant_type,
            "parent_tenant_id": str(self.parent_tenant_id) if self.parent_tenant_id else None,
            "created_by_user_id": str(self.created_by_user_id) if self.created_by_user_id else None,
        }
    
    @classmethod
    def create(
        cls,
        tenant_id: TenantId,
        name: str,
        slug: str,
        tenant_type: str,
        parent_tenant_id: Optional[TenantId] = None,
        created_by_user_id: Optional[UUID] = None,
    ) -> "TenantCreated":
        """Factory method to create event with generated ID and timestamp."""
        return cls(
            id=uuid4(),
            occurred_at=datetime.utcnow(),
            tenant_id=tenant_id,
            name=name,
            slug=slug,
            tenant_type=tenant_type,
            parent_tenant_id=parent_tenant_id,
            created_by_user_id=created_by_user_id,
        )


@dataclass(frozen=True, slots=True)
class TenantActivated:
    """
    Event fired when a tenant is activated.
    
    Enables downstream services to start processing for this tenant.
    """
    
    id: UUID
    occurred_at: datetime
    tenant_id: TenantId
    activated_by_user_id: Optional[UUID]
    
    def as_dict(self) -> Dict[str, Any]:
        """Convert event to dictionary for serialization."""
        return {
            "id": str(self.id),
            "occurred_at": self.occurred_at.isoformat(),
            "tenant_id": str(self.tenant_id),
            "activated_by_user_id": str(self.activated_by_user_id) if self.activated_by_user_id else None,
        }
    
    @classmethod
    def create(
        cls,
        tenant_id: TenantId,
        activated_by_user_id: Optional[UUID] = None,
    ) -> "TenantActivated":
        """Factory method to create event with generated ID and timestamp."""
        return cls(
            id=uuid4(),
            occurred_at=datetime.utcnow(),
            tenant_id=tenant_id,
            activated_by_user_id=activated_by_user_id,
        )


@dataclass(frozen=True, slots=True)
class TenantDeactivated:
    """
    Event fired when a tenant is deactivated.
    
    Signals downstream services to stop processing and potentially archive data.
    """
    
    id: UUID
    occurred_at: datetime
    tenant_id: TenantId
    deactivated_by_user_id: Optional[UUID]
    reason: Optional[str]
    
    def as_dict(self) -> Dict[str, Any]:
        """Convert event to dictionary for serialization."""
        return {
            "id": str(self.id),
            "occurred_at": self.occurred_at.isoformat(),
            "tenant_id": str(self.tenant_id),
            "deactivated_by_user_id": str(self.deactivated_by_user_id) if self.deactivated_by_user_id else None,
            "reason": self.reason,
        }
    
    @classmethod
    def create(
        cls,
        tenant_id: TenantId,
        deactivated_by_user_id: Optional[UUID] = None,
        reason: Optional[str] = None,
    ) -> "TenantDeactivated":
        """Factory method to create event with generated ID and timestamp."""
        return cls(
            id=uuid4(),
            occurred_at=datetime.utcnow(),
            tenant_id=tenant_id,
            deactivated_by_user_id=deactivated_by_user_id,
            reason=reason,
        )


@dataclass(frozen=True, slots=True)
class TenantUpdated:
    """
    Event fired when tenant properties are updated.
    
    Contains before and after snapshots for audit purposes.
    """
    
    id: UUID
    occurred_at: datetime
    tenant_id: TenantId
    updated_by_user_id: Optional[UUID]
    changed_fields: Dict[str, Any]
    previous_values: Dict[str, Any]
    
    def __post_init__(self) -> None:
        """Validate event data."""
        if not self.changed_fields:
            raise ValueError("At least one field must be changed")
    
    def as_dict(self) -> Dict[str, Any]:
        """Convert event to dictionary for serialization."""
        return {
            "id": str(self.id),
            "occurred_at": self.occurred_at.isoformat(),
            "tenant_id": str(self.tenant_id),
            "updated_by_user_id": str(self.updated_by_user_id) if self.updated_by_user_id else None,
            "changed_fields": self.changed_fields,
            "previous_values": self.previous_values,
        }
    
    @classmethod
    def create(
        cls,
        tenant_id: TenantId,
        changed_fields: Dict[str, Any],
        previous_values: Dict[str, Any],
        updated_by_user_id: Optional[UUID] = None,
    ) -> "TenantUpdated":
        """Factory method to create event with generated ID and timestamp."""
        return cls(
            id=uuid4(),
            occurred_at=datetime.utcnow(),
            tenant_id=tenant_id,
            updated_by_user_id=updated_by_user_id,
            changed_fields=changed_fields,
            previous_values=previous_values,
        )
    
@dataclass(frozen=True, slots=True)
class TenantSuspended(EventBase):
    tenant_id: TenantId = TenantId(uuid4())
    actor_id: Optional[UserId] = None
    reason: Optional[str] = None
    until: Optional[datetime] = None  # optional suspension end


@dataclass(frozen=True, slots=True)
class TenantPlanChanged(EventBase):
    tenant_id: TenantId = TenantId(uuid4())
    from_plan_id: Optional[PlanId] = None
    from_plan_slug: Optional[str] = None
    to_plan_id: Optional[PlanId] = None
    to_plan_slug: Optional[str] = None
    actor_id: Optional[UserId] = None
    effective_at: Optional[datetime] = None
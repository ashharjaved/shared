# src/identity/domain/entities/tenant.py
"""Tenant aggregate root."""

from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID, uuid4

from ..types import TenantId, TenantType
from ..value_objects import Name, Slug, Timestamps
from ..errors import InvariantViolation


@dataclass(slots=True)
class Tenant:
    """Tenant aggregate root representing organizational hierarchy."""
    
    id: TenantId
    name: Name
    slug: Slug
    tenant_type: TenantType
    parent_tenant_id: TenantId | None
    is_active: bool
    timestamps: Timestamps
    
    def __post_init__(self) -> None:
        """Validate tenant invariants."""
        if self.parent_tenant_id == self.id:
            raise InvariantViolation("Tenant cannot be its own parent")
        
        if self.tenant_type == 'platform' and self.parent_tenant_id is not None:
            raise InvariantViolation("Root tenant cannot have parent")
        
        if self.tenant_type != 'root' and self.parent_tenant_id is None:
            raise InvariantViolation("Non-root tenant must have parent")
    
    @classmethod
    def create_root(
        cls,
        name: str,
        slug: str | None = None,
    ) -> 'Tenant':
        """Create root tenant."""
        name_vo = Name(name)
        slug_vo = Slug(slug) if slug else Slug.from_name(name)
        
        return cls(
            id=TenantId(uuid4()),
            name=name_vo,
            slug=slug_vo,
            tenant_type='platform',
            parent_tenant_id=None,
            is_active=True,
            timestamps=Timestamps.now(),
        )
    
    @classmethod
    def create_reseller(
        cls,
        name: str,
        slug: str | None = None,
    ) -> 'Tenant':
        """Create reseller tenant."""
        name_vo = Name(name)
        slug_vo = Slug(slug) if slug else Slug.from_name(name)
        
        return cls(
            id=TenantId(uuid4()),
            name=name_vo,
            slug=slug_vo,
            tenant_type='reseller',
            parent_tenant_id=None,  # to be set when attached under a root in app layer
            is_active=True,
            timestamps=Timestamps.now(),
        )
    
    @classmethod
    def create_child(
        cls,
        name: str,
        tenant_type: TenantType,
        parent_tenant_id: TenantId,
        slug: str | None = None,
    ) -> 'Tenant':
        """Create child tenant (reseller or tenant)."""
        if tenant_type == 'root':
            raise InvariantViolation("Use create_root() for root tenants")
        if parent_tenant_id is None:
            raise InvariantViolation("Child tenant must have parent_tenant_id")
        
        name_vo = Name(name)
        slug_vo = Slug(slug) if slug else Slug.from_name(name)
        
        return cls(
            id=TenantId(uuid4()),
            name=name_vo,
            slug=slug_vo,
            tenant_type=tenant_type,
            parent_tenant_id=parent_tenant_id,
            is_active=True,
            timestamps=Timestamps.now(),
        )
    
    def activate(self) -> None:
        """Activate tenant."""
        if self.is_active:
            return
        
        self.is_active = True
        self._update_timestamp()
    
    def deactivate(self) -> None:
        """Deactivate tenant."""
        if not self.is_active:
            return
        
        self.is_active = False
        self._update_timestamp()
    
    def is_root(self) -> bool:
        """Check if this is a root tenant."""
        return self.tenant_type == 'root'
    
    def can_have_child_type(self, child_type: TenantType) -> bool:
        """Check if this tenant can have a child of given type."""
        if self.tenant_type == 'root':
            return child_type in {'reseller', 'tenant'}
        elif self.tenant_type == 'reseller':
            return child_type == 'tenant'
        else:
            return False  # Regular tenants cannot have children
    
    def _update_timestamp(self) -> None:
        """Update the updated_at timestamp."""
        self.timestamps = self.timestamps.update_timestamp()

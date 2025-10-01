# src/identity/domain/entities/tenant.py

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Optional
from uuid import UUID


class TenantType(str, Enum):
    PLATFORM = "PLATFORM"
    RESELLER = "RESELLER"
    TENANT = "TENANT"

class SubscriptionPlan(str, Enum):
    FREE = "FREE"
    BASIC = "BASIC"
    PREMIUM = "PREMIUM"
    ENTERPRISE = "ENTERPRISE"

@dataclass(frozen=True)
class Tenant:
    """
    Domain entity representing a tenant in the multi-tenant system.
    
    A tenant can be:
    - PLATFORM: The root platform tenant
    - RESELLER: A reseller managing multiple tenant tenants
    - TENANT: An end tenant tenant using the platform
    """
    id: UUID
    name: str
    type: TenantType
    parent_tenant_id: Optional[UUID]
    is_active: bool
    created_at: datetime
    updated_at: datetime
    remarks: Optional[str] = None
    
    def __post_init__(self) -> None:
        """Validate tenant invariants."""
        if not self.name or not self.name.strip():
            raise ValueError("Tenant name cannot be empty")
            
        if self.type == TenantType.PLATFORM and self.parent_tenant_id is not None:
            raise ValueError("Platform tenant cannot have a parent")
            
        if self.type in (TenantType.RESELLER, TenantType.TENANT) and self.parent_tenant_id is None:
            raise ValueError(f"{self.type} tenant must have a parent")
    
    def is_platform(self) -> bool:
        """Check if this is the platform tenant."""
        return self.type == TenantType.PLATFORM
    
    def is_reseller(self) -> bool:
        """Check if this is a reseller tenant."""
        return self.type == TenantType.RESELLER
    
    def is_tenant(self) -> bool:
        """Check if this is a tenant tenant."""
        return self.type == TenantType.TENANT
    
    def can_have_children(self) -> bool:
        """Check if this tenant type can have child tenants."""
        return self.type in (TenantType.PLATFORM, TenantType.RESELLER)
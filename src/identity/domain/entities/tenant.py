# src/identity/domain/entities/tenant.py

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Optional
from uuid import UUID


class TenantType(str, Enum):
    PLATFORM_OWNER = "PLATFORM_OWNER"
    RESELLER = "RESELLER"
    CLIENT = "CLIENT"

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
    - RESELLER: A reseller managing multiple client tenants
    - CLIENT: An end client tenant using the platform
    """
    id: UUID
    name: str
    type: TenantType
    parent_tenant_id: Optional[UUID]
    plan: Optional[SubscriptionPlan]
    is_active: bool
    created_at: datetime
    updated_at: datetime
    
    def __post_init__(self) -> None:
        """Validate tenant invariants."""
        if not self.name or not self.name.strip():
            raise ValueError("Tenant name cannot be empty")
            
        if self.type == TenantType.PLATFORM_OWNER and self.parent_tenant_id is not None:
            raise ValueError("Platform tenant cannot have a parent")
            
        if self.type in (TenantType.RESELLER, TenantType.CLIENT) and self.parent_tenant_id is None:
            raise ValueError(f"{self.type} tenant must have a parent")
    
    def is_platform(self) -> bool:
        """Check if this is the platform tenant."""
        return self.type == TenantType.PLATFORM_OWNER
    
    def is_reseller(self) -> bool:
        """Check if this is a reseller tenant."""
        return self.type == TenantType.RESELLER
    
    def is_client(self) -> bool:
        """Check if this is a client tenant."""
        return self.type == TenantType.CLIENT
    
    def can_have_children(self) -> bool:
        """Check if this tenant type can have child tenants."""
        return self.type in (TenantType.PLATFORM_OWNER, TenantType.RESELLER)
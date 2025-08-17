from __future__ import annotations
from dataclasses import dataclass
from typing import List, Optional

# Tenants
@dataclass
class CreateTenant:
    name: str
    tenant_type: str = "CLIENT"
    subscription_plan: str = "basic"
    billing_email: Optional[str] = None

@dataclass
class UpdateTenant:
    tenant_id: UUID
    name: Optional[str] = None
    tenant_type: Optional[str] = None
    subscription_plan: Optional[str] = None
    billing_email: Optional[str] = None

@dataclass
class UpdateTenantStatus:
    tenant_id: UUID
    is_active: Optional[bool] = None
    subscription_status: Optional[str] = None

# Users
@dataclass
class CreateUser:
    tenant_id: UUID
    email: str
    password: str
    roles: List[str]

@dataclass
class AssignRole:
    tenant_id: UUID
    user_id: str
    role: str

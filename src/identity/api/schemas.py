from __future__ import annotations
from typing import Optional
from pydantic import BaseModel, EmailStr, Field
from uuid import UUID

# ---- Tenants ----
class TenantCreate(BaseModel):
    name: str = Field(min_length=2, max_length=255)
    tenant_type: str = "CLIENT"  # PLATFORM_OWNER | RESELLER | CLIENT
    subscription_plan: str = "BASIC"  # BASIC | PREMIUM | ENTERPRISE
    billing_email: Optional[EmailStr] = None

class TenantUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=2, max_length=255)
    tenant_type: Optional[str] = None
    subscription_plan: Optional[str] = None
    billing_email: Optional[EmailStr] = None

class TenantStatusUpdate(BaseModel):
    is_active: Optional[bool] = None
    subscription_status: Optional[str] = None  # e.g., ACTIVE, SUSPENDED, PAST_DUE

class TenantRead(BaseModel):
    id: UUID
    name: str
    tenant_type: str
    subscription_status: str
    is_active: bool

# ---- Users ----
class UserCreate(BaseModel):
    tenant_id: Optional[UUID] = None
    email: EmailStr
    password: str = Field(min_length=8)
    role: str = "STAFF"

class UserRead(BaseModel):
    id: UUID
    tenant_id: UUID
    email: EmailStr
    role: str
    is_active: bool
    is_verified: bool

# ---- Token ----
class TokenRequest(BaseModel):
    email: EmailStr
    password: str

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int

# src/identity/api/schemas.py
from __future__ import annotations
from datetime import datetime
from typing import Optional
from uuid import UUID
from pydantic import BaseModel, EmailStr, Field, ConfigDict, AliasChoices

from src.identity.domain.entities.tenant import SubscriptionPlan, TenantType

class LoginRequest(BaseModel):
    tenant_id: UUID
    email: EmailStr
    password: str = Field(min_length=6, max_length=256)


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    refresh_token: Optional[str] = None

class UserCreate(BaseModel):
    tenant_id: UUID
    name: str = Field(min_length=2, max_length=200)
    email: EmailStr
    password: str = Field(min_length=6, max_length=256)
    role: str = Field(description="One of SUPER_ADMIN, RESELLER_ADMIN, TENANT_ADMIN, STAFF")

class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    email: EmailStr
    role: str
    is_active: bool
    is_verified: bool = False
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True, extra="forbid")


class TenantCreate(BaseModel):
    name: str = Field(min_length=2, max_length=200)
    tenant_type: str = Field(description="One of PLATFORM, RESELLER, CLIENT")
    parent_tenant_id: Optional[str] = Field(default=None)
    subscription_plan: str


class TenantRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    tenant_type: TenantType = Field(validation_alias=AliasChoices('tenant_type', 'type'))
    subscription_plan: SubscriptionPlan = Field(validation_alias=AliasChoices('subscription_plan', 'plan'))
    is_active: bool
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


# Optional helper for refresh/logout flows (used by auth routes)
class RefreshRequest(BaseModel):
    refresh_token: str


class TenantStatusUpdate(BaseModel):
    is_active: bool

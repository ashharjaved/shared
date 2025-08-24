from __future__ import annotations
from dataclasses import dataclass
from pydantic import BaseModel, EmailStr, Field
from uuid import UUID
from enum import StrEnum

class TenantType(StrEnum):
    PLATFORM_OWNER = "PLATFORM_OWNER"
    CLIENT = "CLIENT"
    RESELLER = "RESELLER"

class SubscriptionPlan(StrEnum):
    BASIC = "BASIC"
    STANDARD = "STANDARD"
    ENTERPRISE = "ENTERPRISE"

class SubscriptionStatus(StrEnum):
    ACTIVE    = "ACTIVE"
    PAST_DUE  = "PAST_DUE"
    SUSPENDED = "SUSPENDED"
    CANCELLED = "CANCELLED"

# ==========================================================
# RBAC Role Enum
# ==========================================================
class Role(StrEnum):
    SUPER_ADMIN = "SUPER_ADMIN"
    RESELLER_ADMIN = "RESELLER_ADMIN"
    TENANT_ADMIN = "TENANT_ADMIN"
    STAFF = "STAFF"

@dataclass(frozen=True)
class EmailAddress:
    value: str


class AdminCreateUserDTO(BaseModel):
    email: EmailStr
    role: Role
    password: str = Field(min_length=8, max_length=128)


class LoginDTO(BaseModel):
    tenant_name: str = Field(min_length=1, max_length=255)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class ChangePasswordDTO(BaseModel):
    old_password: str = Field(min_length=8, max_length=128)
    new_password: str = Field(min_length=8, max_length=128)

class UserPublic(BaseModel):
    id: UUID
    tenant_id: UUID
    email: EmailStr
    role: Role
    is_active: bool
    is_verified: bool

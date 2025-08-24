from __future__ import annotations

from pydantic import BaseModel, EmailStr, Field
from uuid import UUID
from src.shared.security import Role


class BootstrapRequest(BaseModel):
    tenant_name: str = Field(min_length=1, max_length=255)
    owner_email: EmailStr
    owner_password: str = Field(min_length=8, max_length=128)
    billing_email: EmailStr | None = None


class BootstrapResponse(BaseModel):
    tenant_id: UUID
    owner_user_id: UUID
    tenant_name: str


class AdminCreateUserRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    role: Role


class AdminCreateUserResponse(BaseModel):
    id: UUID
    email: EmailStr
    role: Role
    tenant_id: UUID


class LoginRequest(BaseModel):
    tenant_name: str
    email: EmailStr
    password: str


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class MeResponse(BaseModel):
    id: UUID
    tenant_id: UUID
    email: EmailStr
    role: Role
    is_active: bool
    is_verified: bool


class ChangePasswordRequest(BaseModel):
    old_password: str
    new_password: str


class SuccessResponse(BaseModel):
    ok: bool = True

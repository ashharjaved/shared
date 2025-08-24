from __future__ import annotations

from pydantic import BaseModel, EmailStr, Field
from src.shared.security import Role


class BootstrapPlatform(BaseModel):
    tenant_name: str = Field(min_length=1, max_length=255)
    owner_email: EmailStr
    owner_password: str = Field(min_length=8, max_length=128)
    billing_email: EmailStr | None = None


class CreateUser(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    role: Role

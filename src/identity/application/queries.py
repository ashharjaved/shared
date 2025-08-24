from __future__ import annotations

from uuid import UUID
from pydantic import BaseModel, EmailStr
from src.shared.security import Role


class MeDTO(BaseModel):
    id: UUID
    tenant_id: UUID
    email: EmailStr
    role: Role
    is_active: bool
    is_verified: bool

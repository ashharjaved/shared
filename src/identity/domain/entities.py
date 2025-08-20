from __future__ import annotations
from dataclasses import dataclass
from typing import List
from uuid import UUID
from pydantic import BaseModel, Field
from src.identity.domain.value_objects import UserRole


@dataclass(frozen=True)
class Principal(BaseModel):
    user_id: UUID | None = None
    tenant_id: UUID | None = None
    email: str | None = None
    roles: set[str] = Field(default_factory=set)

    def has_any_role(self, *want: str) -> bool:
        want_u = {r.upper() for r in want}
        return any(r in self.roles for r in want_u)
     

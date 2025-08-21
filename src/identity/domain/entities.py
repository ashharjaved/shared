from __future__ import annotations
from uuid import UUID
from pydantic import BaseModel, Field, ConfigDict

class Principal(BaseModel):
    model_config = ConfigDict(frozen=True)
    user_id: UUID | None = None
    tenant_id: UUID
    email: str | None = None
    role: set[str] = Field(default_factory=set)


    def has_any_role(self, *want: str) -> bool:
        want_u = {r.upper() for r in want}
        return any(r in self.role for r in want_u)
     

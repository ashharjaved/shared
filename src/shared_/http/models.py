from __future__ import annotations
from typing import Optional, Set
from pydantic import BaseModel, EmailStr

class CurrentUser(BaseModel):
    id: str
    email: EmailStr | str
    tenant_id: Optional[str] = None
    roles: Set[str] = set()

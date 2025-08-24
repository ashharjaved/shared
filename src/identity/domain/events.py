from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class UserCreated:
    tenant_id: UUID
    user_id: UUID

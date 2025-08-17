from __future__ import annotations
from dataclasses import dataclass
from typing import List

ROLES = {"SUPER_ADMIN", "RESELLER_ADMIN", "TENANT_ADMIN", "STAFF"}

@dataclass(frozen=True)
class Principal:
    user_id: str
    tenant_id: str
    roles: List[str]

    def has_any_role(self, *allowed: str) -> bool:
        return any(r in self.roles for r in allowed)


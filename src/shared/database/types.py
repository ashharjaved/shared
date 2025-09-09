from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional

@dataclass(slots=True)
class TenantContext:
    tenant_id: Optional[str] = None
    user_id: Optional[str] = None
    roles: List[str] = field(default_factory=list)

    @classmethod
    def from_maybe(
        cls,
        tenant_id: Optional[str],
        user_id: Optional[str],
        roles: Optional[list[str]],
    ) -> "TenantContext":
        return cls(
            tenant_id=tenant_id,
            user_id=user_id,
            roles=roles if roles is not None else [],
        )
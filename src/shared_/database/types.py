from __future__ import annotations
from dataclasses import replace as dc_replace
from dataclasses import dataclass, field
from typing import List, Optional, overload

@dataclass(slots=True)
class TenantContext:
    tenant_id: Optional[str] = None
    user_id: Optional[str] = None
    roles: List[str] = field(default_factory=list)

    @overload
    @classmethod
    def from_maybe(cls, tenant_id: str) -> "TenantContext":
        ...

    @overload
    @classmethod
    def from_maybe(
        cls,
        tenant_id: Optional[str],
        user_id: Optional[str] = None,
        roles: Optional[list[str]] = None,
    ) -> "TenantContext":
        ...

    @classmethod
    def from_maybe(
        cls,
        tenant_id: Optional[str] = None,
        user_id: Optional[str] = None,
        roles: Optional[list[str]] = None,
    ) -> "TenantContext":
        if isinstance(tenant_id, str) and user_id is None and roles is None:
            return cls(tenant_id=tenant_id, user_id=None, roles=[])
        return cls(
            tenant_id=tenant_id,
            user_id=user_id,
            roles=roles if roles is not None else [],
        )
    
    def replace(self, **kwargs) -> "TenantContext":
        """
        Return a new TenantContext with updated fields, leaving others unchanged.
        Example:
            ctx2 = ctx.replace(tenant_id="new-id")
        """
        return dc_replace(self, **kwargs)
### Begin: src/conversation/domain/repositories/flow_repository.py ***
from __future__ import annotations

from typing import Protocol, Optional
from uuid import UUID

from ..entities import MenuFlow

class FlowRepository(Protocol):
    """
    Tenant-scoped flow repository.
    Implementations must enforce RLS by running under the correct GUCs.
    """

    async def get_default(self, *, industry_type: Optional[str] = None) -> MenuFlow:
        """
        Returns the default flow for the tenant (optionally filtered by industry).
        Raises FlowNotFoundError if missing.
        """
        ...

    async def get_by_id(self, flow_id: UUID) -> MenuFlow:  # noqa: D401
        """Returns a flow by its identifier or raises FlowNotFoundError."""
        ...

    async def get_by_name(self, *, name: str, version: Optional[int] = None) -> MenuFlow:
        """
        Returns a flow by (name[, version]).
        If version is None, implementation may pick the highest active version.
        Raises FlowNotFoundError on absence.
        """
        ...

    async def list(
        self,
        *,
        active: Optional[bool] = None,
        name: Optional[str] = None,
        industry_type: Optional[str] = None,
    ) -> list[MenuFlow]:
        """
        Lists flows for the tenant with optional filters.
        """
        ...

    async def create(self, flow: MenuFlow) -> MenuFlow:
        """
        Persists a new flow. Must honor unique (tenant_id, name, version).
        When setting is_default=True, must ensure only one default per (tenant, industry).
        """
        ...

    async def update(self, flow: MenuFlow) -> MenuFlow:
        """Updates mutable fields (is_active, is_default, definition, etc.)."""
        ...

    async def toggle_default(self, flow_id: UUID, *, industry_type: Optional[str]) -> None:
        """
        Sets the given flow as default for the (tenant, industry_type) and unsets others.
        """
        ...
### End: src/conversation/domain/repositories/flow_repository.py ***

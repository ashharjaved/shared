from __future__ import annotations

import json
from typing import Any, Optional, Tuple
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from ..entities import (
    TenantConfigView,
    SetConfigDTO,
    DeleteConfigDTO,
    ResolvedConfigDTO,
    ConfigSourceLevel,
)
from .configuration_service import ConfigRepository, assert_rls_set
from ...infrastructure.cache import ConfigCache


class TenantContextService:
    """
    Utility to set/check Postgres GUCs for RLS.
    Typically the middleware/dependencies set these once per request.
    This service is available for explicit control in jobs/tests.
    """

    @staticmethod
    async def set_gucs(session: AsyncSession, *, tenant_id: UUID, user_id: Optional[UUID] = None, roles_csv: str = "") -> None:
        await session.execute(
            # SET LOCAL scope lives for the current transaction
            # nosec - values are bound-parameters
            text("SET LOCAL app.jwt_tenant = :t"),
            {"t": str(tenant_id)},
        )
        if user_id is not None:
            await session.execute(text("SET LOCAL app.user_id = :u"), {"u": str(user_id)})
        if roles_csv:
            await session.execute(text("SET LOCAL app.roles = :r"), {"r": roles_csv})


# Local import to avoid circulars (sqlalchemy.text)
from sqlalchemy import text  # noqa: E402

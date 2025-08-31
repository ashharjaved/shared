from __future__ import annotations

from typing import Optional
from uuid import UUID

from sqlalchemy import and_, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from src.platform.domain.entities.rate_limit_policy import RateLimitPolicy, RateLimitScope
from src.platform.domain.repositories.rate_limit_repository import RateLimitRepository
from src.shared.exceptions import RlsNotSetError
from src.platform.infrastructure.models.Tenant_config_model import RateLimitPolicyORM, assert_rls_context


def _to_domain(row: RateLimitPolicyORM) -> RateLimitPolicy:
    return RateLimitPolicy(
        id=row.id,
        tenant_id=row.tenant_id,
        scope=RateLimitScope(row.scope),
        requests_per_minute=row.requests_per_minute,
        burst_limit=row.burst_limit,
        created_at=row.created_at,
        updated_at=row.updated_at,
        deleted_at=row.deleted_at,
    )


class RateLimitRepositoryImpl(RateLimitRepository):
    """
    SQLAlchemy 2.x async implementation honoring RLS and GLOBAL rows (tenant_id IS NULL).
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def _ensure_rls(self) -> None:
        try:
            await assert_rls_context(self._session)
        except PermissionError as e:
            raise RlsNotSetError(str(e)) from e

    async def get_for_tenant(self, tenant_id: UUID) -> Optional[RateLimitPolicy]:
        await self._ensure_rls()
        stmt = (
            select(RateLimitPolicyORM)
            .where(
                and_(
                    RateLimitPolicyORM.tenant_id == tenant_id,
                    RateLimitPolicyORM.scope == RateLimitScope.TENANT.value,
                    RateLimitPolicyORM.deleted_at.is_(None),
                )
            )
            .limit(1)
        )
        row = (await self._session.execute(stmt)).scalars().first()
        return _to_domain(row) if row else None

    async def get_global(self) -> Optional[RateLimitPolicy]:
        await self._ensure_rls()
        stmt = (
            select(RateLimitPolicyORM)
            .where(
                and_(
                    RateLimitPolicyORM.tenant_id.is_(None),
                    RateLimitPolicyORM.scope == RateLimitScope.GLOBAL.value,
                    RateLimitPolicyORM.deleted_at.is_(None),
                )
            )
            .limit(1)
        )
        row = (await self._session.execute(stmt)).scalars().first()
        return _to_domain(row) if row else None

    async def upsert_tenant_policy(
        self, tenant_id: UUID, requests_per_minute: int, burst_limit: int
    ) -> RateLimitPolicy:
        await self._ensure_rls()
        stmt = (
            insert(RateLimitPolicyORM)
            .values(
                tenant_id=tenant_id,
                scope=RateLimitScope.TENANT.value,
                requests_per_minute=requests_per_minute,
                burst_limit=burst_limit,
            )
            .on_conflict_do_update(
                index_elements=[RateLimitPolicyORM.tenant_id, RateLimitPolicyORM.scope],
                set_=dict(
                    requests_per_minute=requests_per_minute,
                    burst_limit=burst_limit,
                ),
            )
            .returning(RateLimitPolicyORM)
        )
        row = (await self._session.execute(stmt)).scalars().first()
        if row is None:
            raise RuntimeError("Upsert failed to update existing row")
        return _to_domain(row)

    async def upsert_global_policy(
        self, requests_per_minute: int, burst_limit: int
    ) -> RateLimitPolicy:
        await self._ensure_rls()
        stmt = (
            insert(RateLimitPolicyORM)
            .values(
                tenant_id=None,
                scope=RateLimitScope.GLOBAL.value,
                requests_per_minute=requests_per_minute,
                burst_limit=burst_limit,
            )
            .on_conflict_do_update(
                index_elements=[RateLimitPolicyORM.tenant_id, RateLimitPolicyORM.scope],
                set_=dict(
                    requests_per_minute=requests_per_minute,
                    burst_limit=burst_limit,
                ),
            )
            .returning(RateLimitPolicyORM)
        )
        row = (await self._session.execute(stmt)).scalars().first()
        if row is None:
            raise RuntimeError("Upsert failed to update existing row")
        return _to_domain(row)
from __future__ import annotations

from datetime import datetime, timezone
from typing import Dict, Iterable, Optional, Tuple
from uuid import UUID

from sqlalchemy import and_, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from src.platform.domain.entities.tenant_config import TenantConfiguration, ConfigType
from src.shared.exceptions import RlsNotSetError
from src.platform.domain.repositories.config_repo import ConfigRepository
from ...domain.value_objects.config_key import ConfigKey
from src.platform.infrastructure.models.Tenant_config_model import TenantConfigurationORM, assert_rls_context


def _to_domain(row: TenantConfigurationORM) -> TenantConfiguration:
    return TenantConfiguration(
        id=row.id,
        tenant_id=row.tenant_id,
        key=ConfigKey(row.config_key),
        value=row.config_value,
        config_type=ConfigType(row.config_type),
        is_encrypted=row.is_encrypted,
        created_at=row.created_at,
        updated_at=row.updated_at,
        deleted_at=row.deleted_at,
    )


class ConfigRepositoryImpl(ConfigRepository):
    """
    SQLAlchemy 2.x async implementation.
    Relies on DB RLS; NEVER queries without tenant GUC.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def _ensure_rls(self) -> None:
        try:
            await assert_rls_context(self._session)
        except PermissionError as e:
            raise RlsNotSetError(str(e)) from e

    async def get(self, tenant_id: UUID, key: ConfigKey) -> Optional[TenantConfiguration]:
        await self._ensure_rls()
        stmt = (
            select(TenantConfigurationORM)
            .where(
                and_(
                    TenantConfigurationORM.tenant_id == tenant_id,
                    TenantConfigurationORM.config_key == str(key),
                    TenantConfigurationORM.deleted_at.is_(None),
                )
            )
            .limit(1)
        )
        row = (await self._session.execute(stmt)).scalars().first()
        return _to_domain(row) if row else None

    async def list_by_prefix(
        self, tenant_id: UUID, prefix: str, limit: int = 100, offset: int = 0
    ) -> Iterable[TenantConfiguration]:
        await self._ensure_rls()
        stmt = (
            select(TenantConfigurationORM)
            .where(
                and_(
                    TenantConfigurationORM.tenant_id == tenant_id,
                    TenantConfigurationORM.config_key.startswith(prefix),
                    TenantConfigurationORM.deleted_at.is_(None),
                )
            )
            .order_by(TenantConfigurationORM.config_key.asc())
            .limit(limit)
            .offset(offset)
        )
        rows = (await self._session.execute(stmt)).scalars().all()
        return [_to_domain(r) for r in rows]

    async def upsert(
        self,
        tenant_id: UUID,
        key: ConfigKey,
        value: Dict,
        config_type: ConfigType,
        is_encrypted: bool,
    ) -> TenantConfiguration:
        await self._ensure_rls()
        stmt = (
            insert(TenantConfigurationORM)
            .values(
                tenant_id=tenant_id,
                config_key=str(key),
                config_value=value,
                config_type=config_type.value,
                is_encrypted=is_encrypted,
            )
            .on_conflict_do_update(
                index_elements=[TenantConfigurationORM.tenant_id, TenantConfigurationORM.config_key],
                set_=dict(
                    config_value=value,
                    config_type=config_type.value,
                    is_encrypted=is_encrypted,
                    # updated_at handled by trigger; keeping explicit set is harmless but not required.
                ),
            )
            .returning(TenantConfigurationORM)
        )
        row = (await self._session.execute(stmt)).scalars().first()
        if row is None:
            raise RuntimeError("Upsert failed to create new row")
        # ensure NOT soft-deleted (if previously deleted, unset deleted_at)
        if row.deleted_at is not None:
            upd = (
                update(TenantConfigurationORM)
                .where(TenantConfigurationORM.id == row.id)
                .values(deleted_at=None)
                .returning(TenantConfigurationORM)
            )
            row = (await self._session.execute(upd)).scalars().first()
            if row is None:
                raise RuntimeError("Upsert failed to update existing row")
        return _to_domain(row)

    async def soft_delete(self, tenant_id: UUID, key: ConfigKey) -> bool:
        await self._ensure_rls()
        now = datetime.now(timezone.utc)
        stmt = (
            update(TenantConfigurationORM)
            .where(
                and_(
                    TenantConfigurationORM.tenant_id == tenant_id,
                    TenantConfigurationORM.config_key == str(key),
                    TenantConfigurationORM.deleted_at.is_(None),
                )
            )
            .values(deleted_at=now)
        )
        result = await self._session.execute(stmt)
        return (result.rowcount or 0) > 0

    async def exists_at_or_after(self, tenant_id: UUID, changed_since: datetime) -> bool:
        await self._ensure_rls()
        stmt = (
            select(TenantConfigurationORM.id)
            .where(
                and_(
                    TenantConfigurationORM.tenant_id == tenant_id,
                    TenantConfigurationORM.updated_at >= changed_since,
                    TenantConfigurationORM.deleted_at.is_(None),
                )
            )
            .limit(1)
        )
        return (await self._session.execute(stmt)).first() is not None

    async def get_effective_value_chain(
        self, tenant_id: UUID, key: ConfigKey
    ) -> Tuple[Optional[TenantConfiguration], Optional[TenantConfiguration], Optional[TenantConfiguration]]:
        """
        Fetch potential rows for (client, reseller, platform) scopes.
        NOTE: This implementation returns only the current tenant row; hierarchy resolution
        across reseller/platform requires your tenant tree. In Stage-2 infra we expose the
        per-tenant row and leave cross-tenant lookups to a higher layer with appropriate
        privileges (often via service calls). To avoid violating RLS, we return (client, None, None).
        """
        client = await self.get(tenant_id, key)
        return client, None, None
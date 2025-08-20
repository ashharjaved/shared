from typing import Any, List, Optional, Tuple
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from .models import TenantConfiguration

class ConfigRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get(self, tenant_id: UUID, key: str) -> Optional[Tuple[str, Any]]:
        stmt = (
            select(TenantConfiguration)
            .where(TenantConfiguration.tenant_id == tenant_id)
            .where(TenantConfiguration.config_key == key)
            .where(TenantConfiguration.deleted_at.is_(None))
            .limit(1)
        )
        res = await self.session.execute(stmt)
        row = res.scalar_one_or_none()
        if not row:
            return None
        return (row.config_key, row.config_value)

    async def upsert(self, tenant_id: UUID, key: str, value: Any) -> Tuple[str, Any]:
        # Use Postgres ON CONFLICT on unique (tenant_id, config_key)
        stmt = pg_insert(TenantConfiguration).values(
            tenant_id=tenant_id,
            config_key=key,
            config_value=value,
        ).on_conflict_do_update(
            index_elements=[TenantConfiguration.tenant_id, TenantConfiguration.config_key],
            set_={
                "config_value": value,
                "updated_at": None  # server trigger will set updated_at; keep None to not override
            }
        ).returning(TenantConfiguration.config_key, TenantConfiguration.config_value)
        res = await self.session.execute(stmt)
        key_val = res.one()
        return (key_val[0], key_val[1])

    async def list(self, tenant_id: UUID, limit: int = 50, offset: int = 0) -> List[Tuple[str, Any]]:
        stmt = (
            select(TenantConfiguration.config_key, TenantConfiguration.config_value)
            .where(TenantConfiguration.tenant_id == tenant_id)
            .where(TenantConfiguration.deleted_at.is_(None))
            .order_by(TenantConfiguration.config_key.asc())
            .limit(limit)
            .offset(offset)
        )
        res = await self.session.execute(stmt)
        return [(k, v) for k, v in res.all()]

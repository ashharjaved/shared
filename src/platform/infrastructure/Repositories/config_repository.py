from __future__ import annotations

from dataclasses import asdict
from typing import Any, Optional, Tuple
from uuid import UUID

from sqlalchemy import select, delete, text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.engine import Result
from sqlalchemy.exc import NoResultFound, MultipleResultsFound
from src.platform.domain.entities import (
    TenantConfig,
    ResolvedConfigDTO,
    ConfigType,
    ConfigSourceLevel,
)
from ..models import TenantConfiguration


# --------------------------- RLS Guard ---------------------------

async def assert_rls_set(session: AsyncSession) -> None:
    """
    Ensure the app.jwt_tenant is set; our jwt_tenant() returns NIL UUID if not set.
    """
    res: Result = await session.execute(text("SELECT current_setting('app.jwt_tenant', true)"))
    cur = res.scalar_one_or_none()
    if not cur or cur.strip() == "" or cur.strip() == "00000000-0000-0000-0000-000000000000":
        raise PermissionError("RLS context (app.jwt_tenant) is not set")


# --------------------------- Repository ---------------------------

class ConfigRepository:
    """
    Async repository for tenant_configurations. RLS expected to be active.
    """

    # --- Mutations ---

    async def upsert_config(
            self,
            *,
            session: AsyncSession,
            key: str,
            value: Any,
            config_type: ConfigType = ConfigType.GENERAL,
            is_encrypted: bool = False,
        ) -> TenantConfiguration:
            await assert_rls_set(session)

            stmt = (
                pg_insert(TenantConfiguration)
                .values(
                    tenant_id=text("jwt_tenant()"),  # filled using DB function to respect RLS
                    config_key=key,
                    config_value=value,
                    config_type=config_type,
                    is_encrypted=is_encrypted,
                )
                .on_conflict_do_update(
                    index_elements=["tenant_id", "config_key"],
                    set_={
                        "config_value": value,
                        "config_type": config_type,
                        "is_encrypted": is_encrypted,
                        "updated_at": text("now()"),
                    },
                )
                .returning(TenantConfiguration)
            )
            res = await session.execute(stmt)
            
            try:
                result = res.scalar_one()
                await session.flush()
                return result
            except NoResultFound:
                raise ValueError(f"Failed to upsert configuration for key: {key}")
            except MultipleResultsFound:
                raise ValueError(f"Multiple configurations found for key: {key}")

    async def delete_config(self, *, session: AsyncSession, key: str) -> None:
        await assert_rls_set(session)
        stmt = delete(TenantConfiguration).where(
            TenantConfiguration.config_key == key
        )
        await session.execute(stmt)
        await session.flush()

    # --- Queries (current tenant only) ---

    async def get_config_current(self, *, session: AsyncSession, key: str) -> Optional[TenantConfiguration]:
        await assert_rls_set(session)
        stmt = (
            select(TenantConfiguration)
            .where(
                TenantConfiguration.config_key == key,
                TenantConfiguration.deleted_at.is_(None),
            )
            .limit(1)
        )
        res = await session.execute(stmt)
        row = res.scalar_one_or_none()
        return row

    async def list_configs_current(self, *, session: AsyncSession) -> list[TenantConfiguration]:
        await assert_rls_set(session)
        stmt = (
            select(TenantConfiguration)
            .where(TenantConfiguration.deleted_at.is_(None))
            .order_by(TenantConfiguration.config_key.asc())
        )
        res = await session.execute(stmt)
        rows = res.scalars().all()
        return list(rows)

    # --- Hierarchical Resolution ---

    async def _fetch_tenant_row(self, session: AsyncSession, tenant_id: UUID) -> tuple[str, Optional[UUID]]:
        """
        Read 'tenants' table (platform-scoped, no RLS) to get (tenant_type, parent_tenant_id).
        """
        q = text(
            """
            SELECT tenant_type::text, parent_tenant_id
            FROM tenants
            WHERE id = :tid
            """
        )
        res = await session.execute(q, {"tid": str(tenant_id)})
        row = res.fetchone()
        if not row:
            raise LookupError("Tenant not found")
        return row[0], row[1]

    async def _resolve_chain(self, session: AsyncSession, tenant_id: UUID) -> list[tuple[UUID, ConfigSourceLevel]]:
        """
        Builds [PLATFORM?, RESELLER?, CLIENT?] chain (most generic first).
        """
        ttype, parent = await self._fetch_tenant_row(session, tenant_id)
        chain: list[tuple[UUID, ConfigSourceLevel]] = []

        # Walk up to platform owner
        platform_id: Optional[UUID] = None
        reseller_id: Optional[UUID] = None
        client_id: Optional[UUID] = None

        if ttype == "CLIENT":
            client_id = tenant_id
            if parent:
                # parent expected to be RESELLER
                pt, pparent = await self._fetch_tenant_row(session, parent)
                if pt == "RESELLER":
                    reseller_id = parent
                    # find platform ancestor
                    cur = parent
                    cur_parent = pparent
                    while cur_parent:
                        tt, nxt = await self._fetch_tenant_row(session, cur_parent)
                        if tt == "PLATFORM_OWNER":
                            platform_id = cur_parent
                            break
                        cur = cur_parent
                        cur_parent = nxt
                elif pt == "PLATFORM_OWNER":
                    platform_id = parent  # rare: client directly under platform
        elif ttype == "RESELLER":
            reseller_id = tenant_id
            # climb to platform
            cur_parent = parent
            while cur_parent:
                tt, nxt = await self._fetch_tenant_row(session, cur_parent)
                if tt == "PLATFORM_OWNER":
                    platform_id = cur_parent
                    break
                cur_parent = nxt
        elif ttype == "PLATFORM_OWNER":
            platform_id = tenant_id

        # Build chain order: PLATFORM → RESELLER → CLIENT
        if platform_id:
            chain.append((platform_id, ConfigSourceLevel.PLATFORM))
        if reseller_id:
            chain.append((reseller_id, ConfigSourceLevel.RESELLER))
        if client_id:
            chain.append((client_id, ConfigSourceLevel.CLIENT))
        return chain

    async def _get_for_tenant_with_guc(self, session: AsyncSession, tenant_id: UUID, key: str) -> Optional[TenantConfiguration]:
        """
        Temporarily set app.jwt_tenant to the requested tenant_id, fetch one row, then the caller
        re-sets the original GUC afterward. This respects RLS per level.
        """
        await session.execute(text("SET LOCAL app.jwt_tenant = :t"), {"t": str(tenant_id)})
        stmt = (
            select(TenantConfiguration)
            .where(
                TenantConfiguration.config_key == key,
                TenantConfiguration.deleted_at.is_(None),
            )
            .order_by(TenantConfiguration.updated_at.desc())
            .limit(1)
        )
        res = await session.execute(stmt)
        return res.scalar_one_or_none()

    async def get_config_resolved(self, *, session: AsyncSession, tenant_id: UUID, key: str) -> Optional[ResolvedConfigDTO]:
        """
        Resolution order (first match wins strongest override):
        PLATFORM → RESELLER → CLIENT
        We iterate and keep the last non-null (client overrides reseller overrides platform).
        """
        await assert_rls_set(session)

        # Save current GUC to restore later
        cur_res = await session.execute(text("SELECT current_setting('app.jwt_tenant', true)"))
        original_guc = cur_res.scalar_one_or_none()

        try:
            chain = await self._resolve_chain(session, tenant_id)
            winner: Optional[tuple[TenantConfiguration, ConfigSourceLevel]] = None
            for tid, level in chain:
                row = await self._get_for_tenant_with_guc(session, tid, key)
                if row is not None:
                    winner = (row, level)
            if winner is None:
                return None

            row, level = winner
            return ResolvedConfigDTO(
                config_key=row.config_key,
                config_value=row.config_value,
                config_type=row.config_type,
                is_encrypted=row.is_encrypted,
                source_level=level,
                updated_at=row.updated_at,
            )
        finally:
            # Restore original tenant context for safety
            if original_guc:
                await session.execute(text("SET LOCAL app.jwt_tenant = :t"), {"t": original_guc})

from __future__ import annotations
from typing import Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from dependencies import assert_rls_set
from platform.domain.entities import DeleteConfigDTO, ResolvedConfigDTO, SetConfigDTO, TenantConfigView
from platform.domain.value_objects import ConfigSourceLevel
from platform.infrastructure.Repositories.config_repository import ConfigRepository
from platform.infrastructure.cache import ConfigCache

class ConfigurationService:
    """
    Orchestrates hierarchical resolution + caching + invalidation.
    """
    def __init__(self, repo: ConfigRepository, cache: ConfigCache):
        self.repo = repo
        self.cache = cache

    # ---------- Helpers ----------
    @staticmethod
    def _redact_for_view(resolved: Optional[ResolvedConfigDTO]) -> Optional[TenantConfigView]:
        if resolved is None:
            return None
        return TenantConfigView(
            config_key=resolved.config_key,
            config_value=None if resolved.is_encrypted else resolved.config_value,
            config_type=resolved.config_type,
            is_encrypted=resolved.is_encrypted,
            source_level=resolved.source_level,
            updated_at=resolved.updated_at,
        )

    # ---------- Commands ----------
    async def set_config(self, session: AsyncSession, dto: SetConfigDTO) -> TenantConfigView:
        await assert_rls_set(session)
        saved = await self.repo.upsert_config(
            session=session,
            key=dto.config_key,
            value=dto.config_value,
            config_type=dto.config_type,
            is_encrypted=dto.is_encrypted,
        )
        # Invalidate only the current-tenant key
        await self.cache.delete_config(dto.tenant_id, dto.config_key)

        # Return redacted current-tenant view
        resolved = ResolvedConfigDTO(
            config_key=saved.config_key,
            config_value=saved.config_value,
            config_type=saved.config_type,
            is_encrypted=saved.is_encrypted,
            source_level=ConfigSourceLevel.CLIENT,
            updated_at=saved.updated_at,
        )
        return self._redact_for_view(resolved)

    async def delete_config(self, session: AsyncSession, dto: DeleteConfigDTO) -> None:
        await assert_rls_set(session)
        await self.repo.delete_config(session=session, key=dto.config_key)
        await self.cache.delete_config(dto.tenant_id, dto.config_key)

    # ---------- Queries ----------
    async def get_config_resolved(self, session: AsyncSession, tenant_id: UUID, key: str) -> Optional[TenantConfigView]:
        # Cache (per-tenant, per-key)
        cached = await self.cache.get_config(tenant_id, key)
        if cached is not None:
            # value may be present even if encrypted; redact for API
            return self._redact_for_view(cached)

        await assert_rls_set(session)
        resolved = await self.repo.get_config_resolved(session=session, tenant_id=tenant_id, key=key)
        if resolved is None:
            return None

        # Store in cache (internal form, includes value)
        await self.cache.set_config(tenant_id, key, resolved)
        # Return redacted view
        return self._redact_for_view(resolved)

    async def list_configs_current_tenant(self, session: AsyncSession, tenant_id: UUID) -> list[TenantConfigView]:
        """
        Lists only the current-tenant configs (no hierarchy). Values redacted when encrypted.
        """
        await assert_rls_set(session)
        items = await self.repo.list_configs_current(session=session)
        result: list[TenantConfigView] = []
        for it in items:
            result.append(
                TenantConfigView(
                    config_key=it.config_key,
                    config_value=None if it.is_encrypted else it.config_value,
                    config_type=it.config_type,
                    is_encrypted=it.is_encrypted,
                    source_level=ConfigSourceLevel.CLIENT,
                    updated_at=it.updated_at,
                )
            )
        return result

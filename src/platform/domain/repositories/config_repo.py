from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Dict, Iterable, Optional, Tuple
from uuid import UUID

from src.platform.domain.entities.tenant_config import TenantConfiguration, ConfigType
from src.platform.domain.value_objects.config_key import ConfigKey


class ConfigRepository(ABC):
    """
    Tenant-scoped configuration repository (RLS-protected).
    Implementations MUST NOT bypass RLS and MUST fail if tenant GUC is missing.
    """

    @abstractmethod
    async def get(self, tenant_id: UUID, key: ConfigKey) -> Optional[TenantConfiguration]:
        """Return the current (non-deleted) row for tenant/key or None."""

    @abstractmethod
    async def list_by_prefix(
        self, tenant_id: UUID, prefix: str, limit: int = 100, offset: int = 0
    ) -> Iterable[TenantConfiguration]:
        """List tenant configs by key prefix; excludes soft-deleted."""

    @abstractmethod
    async def upsert(
        self,
        tenant_id: UUID,
        key: ConfigKey,
        value: Dict,
        config_type: ConfigType,
        is_encrypted: bool,
    ) -> TenantConfiguration:
        """
        Insert or update the tenant config. Returns the stored entity.
        Implementations should set updated_at via DB trigger and honor UNIQUE(tenant_id, key).
        """

    @abstractmethod
    async def soft_delete(self, tenant_id: UUID, key: ConfigKey) -> bool:
        """Soft delete the row; returns True if a row was affected."""

    @abstractmethod
    async def exists_at_or_after(self, tenant_id: UUID, changed_since: datetime) -> bool:
        """Lightweight check for changes since timestamp (for cache revalidation)."""

    @abstractmethod
    async def get_effective_value_chain(
        self, tenant_id: UUID, key: ConfigKey
    ) -> Tuple[Optional[TenantConfiguration], Optional[TenantConfiguration], Optional[TenantConfiguration]]:
        """
        Returns a tuple of (client, reseller, platform) rows that exist (excluding soft-deleted).
        Hierarchy resolution is performed by the application service; repository only fetches candidates.
        Note: relies on your tenant hierarchy; this interface returns available rows for callers to resolve.
        """

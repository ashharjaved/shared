from __future__ import annotations

import hashlib
import json
from typing import Any, Dict, Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from src.platform.domain.entities.tenant_config import ConfigType, TenantConfiguration
from src.platform.domain.repositories.config_repo import ConfigRepository
from src.platform.domain.value_objects.config_key import ConfigKey
from src.platform.infrastructure.crypto.crypto_service import CryptoService
from src.platform.infrastructure.repositories.config_repo_impl import ConfigRepositoryImpl
from src.platform.infrastructure.cache.redis_client import RedisClient
from src.platform.application.dtos import ConfigDTO
from .cache_invalidation_service import CacheInvalidationService


class ConfigService:
    """
    Configuration read/write with redaction, envelope encryption, idempotency, and cache.
    Cache keys:
      - cfg:{tenant_id}:{config_key} (JSON; TTL ~5m per policy)
    """

    def __init__(
        self,
        session: AsyncSession,
        redis: RedisClient,
        crypto: CryptoService,
        *,
        ttl_seconds: int = 300,
    ) -> None:
        self._session = session
        self._repo: ConfigRepository = ConfigRepositoryImpl(session)
        self._redis = redis
        self._crypto = crypto
        self._ttl = ttl_seconds
        self._inv = CacheInvalidationService(redis)

    # ---------- helpers ----------

    async def _cache_get(self, tenant_id: str, key: str) -> Optional[Dict[str, Any]]:
        return await self._redis.get_json(f"cfg:{tenant_id}:{key}")

    async def _cache_set(self, tenant_id: str, key: str, payload: Dict[str, Any]) -> None:
        await self._redis.set_json(f"cfg:{tenant_id}:{key}", payload, ttl_seconds=self._ttl)

    def _redact_if_needed(self, entity: TenantConfiguration, *, super_admin: bool) -> Dict[str, Any]:
        if entity.is_encrypted and not super_admin:
            # Standard redaction marker
            return {"redacted": True, "has_value": True}
        return entity.value

    @staticmethod
    def _idempotency_key(tenant_id: str, key: str, value: Optional[Dict[str, Any]]) -> str:
        h = hashlib.sha256()
        h.update(tenant_id.encode("utf-8"))
        h.update(key.encode("utf-8"))
        if value is not None:
            h.update(json.dumps(value, separators=(",", ":"), sort_keys=True).encode("utf-8"))
        return f"idemp:config_mutation:{h.hexdigest()}"

    # ---------- reads ----------

    async def get_config(self, tenant_id: UUID, key: str, *, super_admin: bool) -> Optional[ConfigDTO]:
        # cache-first
        cached = await self._cache_get(str(tenant_id), key)
        if cached is not None:
            return ConfigDTO(
                key=key,
                value=cached["value"],
                is_encrypted=bool(cached.get("is_encrypted", False)),
                config_type=str(cached.get("config_type", "GENERAL")),
                source="tenant",
            )

        entity = await self._repo.get(tenant_id, ConfigKey(key))
        if entity is None or entity.deleted_at is not None:
            return None

        payload = {
            "value": self._redact_if_needed(entity, super_admin=super_admin),
            "is_encrypted": entity.is_encrypted,
            "config_type": entity.config_type.value,
        }
        await self._cache_set(str(tenant_id), key, payload)
        return ConfigDTO(
            key=key,
            value=payload["value"],
            is_encrypted=entity.is_encrypted,
            config_type=entity.config_type.value,
            source="tenant",
        )

    async def resolve_config(self, tenant_id: UUID, key: str, *, super_admin: bool) -> Optional[ConfigDTO]:
        """
        Hierarchy: tenant → parent → platform. RLS prevents cross-tenant reads here.
        In Stage-2, we resolve tenant only; higher-level fallbacks can be injected later.
        """
        return await self.get_config(tenant_id, key, super_admin=super_admin)

    # ---------- writes (idempotent) ----------

    async def set_config(
        self,
        tenant_id: UUID,
        key: str,
        value: Dict[str, Any],
        *,
        is_encrypted: bool,
        config_type: str,
        idempotency_key: Optional[str] = None,
    ) -> ConfigDTO:
        # idempotency (Redis)
        idem_key = idempotency_key or self._idempotency_key(str(tenant_id), key, value)
        # 24h TTL for idempotency memory
        prior = await self._redis.get_json(idem_key)
        if prior is not None:
            # replay
            return ConfigDTO(**prior)

        # encrypt if needed
        to_store = value
        if is_encrypted:
            to_store = self._crypto.encrypt(value)

        entity = await self._repo.upsert(
            tenant_id=tenant_id,
            key=ConfigKey(key),
            value=to_store,
            config_type=ConfigType(config_type),
            is_encrypted=is_encrypted,
        )

        # invalidate cache after commit boundary (DB trigger writes outbox)
        await self._inv.invalidate_key(str(tenant_id), key)

        dto = ConfigDTO(
            key=key,
            value=value if not is_encrypted else {"redacted": True, "has_value": True},
            is_encrypted=is_encrypted,
            config_type=entity.config_type.value,
            source="tenant",
        )
        await self._redis.set_json(idem_key, dto.__dict__, ttl_seconds=86400)
        return dto

    async def delete_config(
        self,
        tenant_id: UUID,
        key: str,
        *,
        idempotency_key: Optional[str] = None,
    ) -> bool:
        idem_key = idempotency_key or self._idempotency_key(str(tenant_id), key, None)
        prior = await self._redis.get_json(idem_key)
        if prior is not None:
            return bool(prior.get("deleted", True))

        ok = await self._repo.soft_delete(tenant_id, ConfigKey(key))
        await self._inv.invalidate_key(str(tenant_id), key)
        await self._redis.set_json(idem_key, {"deleted": ok}, ttl_seconds=86400)
        return ok

from __future__ import annotations

import json
from typing import Optional
from uuid import UUID

from ..domain.entities import ResolvedConfigDTO, ConfigType, ConfigSourceLevel


def _key(tenant_id: UUID, config_key: str) -> str:
    return f"tenant:{tenant_id}:config:{config_key}"


class ConfigCache:
    """
    Thin wrapper over an aioredis-compatible client (from src.shared.cache.get_redis()).
    Stores ResolvedConfigDTO as JSON.
    """
    def __init__(self, redis_client, ttl_seconds: int = 300):
        self._r = redis_client
        self._ttl = ttl_seconds

    async def get_config(self, tenant_id: UUID, config_key: str) -> Optional[ResolvedConfigDTO]:
        raw = await self._r.get(_key(tenant_id, config_key))
        if not raw:
            return None
        data = json.loads(raw)
        return ResolvedConfigDTO(
            config_key=data["config_key"],
            config_value=data["config_value"],
            config_type=ConfigType(data["config_type"]),
            is_encrypted=bool(data["is_encrypted"]),
            source_level=ConfigSourceLevel(data["source_level"]),
            updated_at=None if data.get("updated_at") is None else data["updated_at"],
        )

    async def set_config(self, tenant_id: UUID, config_key: str, dto: ResolvedConfigDTO) -> None:
        payload = json.dumps(
            {
                "config_key": dto.config_key,
                "config_value": dto.config_value,
                "config_type": dto.config_type.value,
                "is_encrypted": dto.is_encrypted,
                "source_level": dto.source_level.value,
                "updated_at": dto.updated_at.isoformat() if dto.updated_at else None,
            }
        )
        await self._r.set(_key(tenant_id, config_key), payload, ex=self._ttl)

    async def delete_config(self, tenant_id: UUID, config_key: str) -> None:
        await self._r.delete(_key(tenant_id, config_key))

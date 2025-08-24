from __future__ import annotations

import logging
from uuid import UUID
from src.config import get_settings
from src.shared.cache import get_cache


logger = logging.getLogger("app.auth")

class LockoutService:
    def __init__(self):
        settings = get_settings()
        self.max_failed = settings.LOCKOUT_MAX_FAILED
        self.cooldown_min = settings.LOCKOUT_COOLDOWN_MIN
        self.cache = get_cache()

    def _key(self, tenant_id: UUID, user_id: UUID) -> str:
        return f"tenant:{tenant_id}:lockout:{user_id}"

    async def is_locked(self, tenant_id: UUID, user_id: UUID) -> bool:
        return bool(await self.cache.get(self._key(tenant_id, user_id)))

    async def lock(self, tenant_id: UUID, user_id: UUID) -> None:
        await self.cache.setex(self._key(tenant_id, user_id), self.cooldown_min * 60, "1")

    async def clear(self, tenant_id: UUID, user_id: UUID) -> None:
        await self.cache.delete(self._key(tenant_id, user_id))
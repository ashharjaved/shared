from typing import Any, List, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from ..infrastructure.repositories import ConfigRepository
from ..infrastructure.cache import get_cache
from ..domain.services import TenantContextService
from src.config import settings

async def handle_set_config(session: AsyncSession, tenant_id: str, key: str, value: Any) -> Tuple[str, Any]:
    repo = ConfigRepository(session)
    k, v = await repo.upsert(tenant_id, key, value)
    cache = get_cache(settings.CONFIG_TTL_SECONDS)
    cache.set(tenant_id, k, v)
    return (k, v)

async def get_config(session: AsyncSession, tenant_id: str, key: str) -> Tuple[str, Any] | None:
    cache = get_cache(settings.CONFIG_TTL_SECONDS)
    cached = cache.get(tenant_id, key)
    if cached is not None:
        return (key, cached)
    repo = ConfigRepository(session)
    res = await repo.get(tenant_id, key)
    if res:
        cache.set(tenant_id, key, res[1])
    return res

async def list_configs(session: AsyncSession, tenant_id: str, limit: int, offset: int) -> List[Tuple[str, Any]]:
    repo = ConfigRepository(session)
    return await repo.list(tenant_id, limit, offset)

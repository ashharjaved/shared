from __future__ import annotations

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status

from sqlalchemy.ext.asyncio import AsyncSession

from src.platform.application.services.config_service import ConfigService
from src.platform.infrastructure.cache.redis_client import RedisClient
from src.platform.infrastructure.crypto.crypto_service import CryptoService
from src.platform.api.schemas import (
    ConfigReadResponse,
    ConfigUpsertRequest,
    ConfigDeleteResponse,
)
from src.dependencies import get_db_session
from src.shared.roles import Role
from src.shared.error_codes import ERROR_CODES

router = APIRouter(prefix="/api/v1/platform/config", tags=["platform:config"])


def _is_super_admin(request: Request) -> bool:
    claims = getattr(request.state, "user_claims", None) or {}
    return str(claims.get("role")) == Role.SUPER_ADMIN.value


async def _service(session: AsyncSession = Depends(get_db_session)) -> ConfigService:
    redis = RedisClient()
    await redis.connect()
    crypto = CryptoService()
    return ConfigService(session, redis, crypto)


def _tenant_id(request: Request) -> UUID:
    claims = getattr(request.state, "user_claims", None)
    if not claims or not claims.get("tenant_id"):
        data = ERROR_CODES["unauthorized"]
        raise HTTPException(status_code=data["http"], detail={"code": "unauthorized", "message": data["message"]})
    return UUID(claims["tenant_id"])


@router.get("/{key}", response_model=ConfigReadResponse)
async def get_config(key: str, request: Request, svc: ConfigService = Depends(_service)):
    tenant_id = _tenant_id(request)
    dto = await svc.get_config(tenant_id, key, super_admin=_is_super_admin(request))
    if dto is None:
        data = ERROR_CODES.get("not_found", {"http": 404, "message": "Not found"})
        raise HTTPException(status_code=404, detail={"code": "not_found", "message": data["message"]})
    return dto.__dict__


@router.get("/resolve/{key}", response_model=ConfigReadResponse)
async def resolve_config(key: str, request: Request, svc: ConfigService = Depends(_service)):
    tenant_id = _tenant_id(request)
    dto = await svc.resolve_config(tenant_id, key, super_admin=_is_super_admin(request))
    if dto is None:
        data = ERROR_CODES.get("not_found", {"http": 404, "message": "Not found"})
        raise HTTPException(status_code=404, detail={"code": "not_found", "message": data["message"]})
    return dto.__dict__


@router.get("", response_model=list[ConfigReadResponse])
async def list_configs(
    request: Request,
    prefix: Optional[str] = None,
    svc: ConfigService = Depends(_service)):
    """
    Simple listing shim: in Stage-2, serve GET by exact key if provided via ?prefix=key,
    otherwise return empty list (full listing typically paginated; omitted here).
    """
    tenant_id = _tenant_id(request)
    if prefix:
        dto = await svc.get_config(tenant_id, prefix, super_admin=_is_super_admin(request))
        return [dto.__dict__] if dto else []
    return []


@router.post("", response_model=ConfigReadResponse)
async def create_config(
    payload: ConfigUpsertRequest,
    request: Request,
    svc: ConfigService = Depends(_service),
    Idempotency_Key: str | None = Header(default=None, alias="Idempotency-Key"),
):
    tenant_id = _tenant_id(request)
    dto = await svc.set_config(
        tenant_id,
        payload.key,
        payload.value,
        is_encrypted=payload.is_encrypted,
        config_type=payload.config_type,
        idempotency_key=Idempotency_Key,
    )
    return dto.__dict__


@router.put("/{key}", response_model=ConfigReadResponse)
async def update_config(
    key: str,
    payload: ConfigUpsertRequest,
    request: Request,
    svc: ConfigService = Depends(_service),
    Idempotency_Key: str | None = Header(default=None, alias="Idempotency-Key"),
):
    tenant_id = _tenant_id(request)
    if key != payload.key:
        raise HTTPException(status_code=422, detail={"code": "invalid_request", "message": "key mismatch"})
    dto = await svc.set_config(
        tenant_id,
        key,
        payload.value,
        is_encrypted=payload.is_encrypted,
        config_type=payload.config_type,
        idempotency_key=Idempotency_Key,
    )
    return dto.__dict__


@router.delete("/{key}", response_model=ConfigDeleteResponse)
async def delete_config(
    key: str,
    request: Request,
    svc: ConfigService = Depends(_service),
    Idempotency_Key: str | None = Header(default=None, alias="Idempotency-Key"),
):
    tenant_id = _tenant_id(request)
    deleted = await svc.delete_config(tenant_id, key, idempotency_key=Idempotency_Key)
    return {"deleted": deleted}


@router.post("/{key}/invalidate")
async def invalidate_config(key: str, request: Request, svc: ConfigService = Depends(_service)):
    tenant_id = _tenant_id(request)
    # best-effort manual invalidation
    from ...application.services.cache_invalidation_service import CacheInvalidationService
    inv = CacheInvalidationService(svc._redis)  # reuse same client
    await inv.invalidate_key(str(tenant_id), key)
    return {"ok": True}
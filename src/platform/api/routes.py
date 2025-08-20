# import logging
# from fastapi import APIRouter, Depends, HTTPException, Query
# from sqlalchemy.ext.asyncio import AsyncSession
# from .schemas import ConfigSetRequest, ConfigItem, ConfigList
# from ..application.handlers import handle_set_config, get_config, list_configs
# from src.platform.domain.services import TenantContextService

# # Dependencies
# from src.shared.security import get_principal  # Stage-1
# from src.dependencies import get_session as get_db_session  # canonical AsyncSession DI

# router = APIRouter(prefix="/api/v1/config", tags=["Platform Config"])

# log = logging.getLogger("platform.config")

# @router.get("/{key}", response_model=ConfigItem)
# async def get_config_item(
#     key: str,
#     principal = Depends(get_principal),
#     session: AsyncSession = Depends(get_db_session),
# ):
#     tenant_id = TenantContextService.get_tenant_id(principal)
#     res = await get_config(session, tenant_id, key)
#     if not res:
#         raise HTTPException(status_code=404, detail="Configuration key not found")
#     k, v = res
#     log.info("config.get", extra={"tenant_id": tenant_id, "key": key})
#     return ConfigItem(key=k, value=v)

# @router.put("/{key}", response_model=ConfigItem)
# async def put_config_item(
#     key: str,
#     payload: ConfigSetRequest,
#     principal = Depends(get_principal),
#     session: AsyncSession = Depends(get_db_session),
# ):
#     if payload.key != key:
#         # keep path param authoritative to avoid accidental mismatch
#         raise HTTPException(status_code=400, detail="Key mismatch between path and body")
#     tenant_id = TenantContextService.get_tenant_id(principal)
#     k, v = await handle_set_config(session, tenant_id, key, payload.value)
#     log.info("config.upsert", extra={"tenant_id": tenant_id, "key": key})
#     return ConfigItem(key=k, value=v)

# @router.get("", response_model=ConfigList)
# async def list_config_items(
#     principal = Depends(get_principal),
#     session: AsyncSession = Depends(get_db_session),
#     limit: int = Query(50, ge=1, le=200),
#     offset: int = Query(0, ge=0),
# ):
#     tenant_id = TenantContextService.get_tenant_id(principal)
#     rows = await list_configs(session, tenant_id, limit, offset)
#     log.info("config.list", extra={"tenant_id": tenant_id, "limit": limit, "offset": offset})
#     return ConfigList(items=[ConfigItem(key=k, value=v) for k, v in rows])
##----------------------------------------------------------------------------------------------
from __future__ import annotations

import logging
from typing import Optional, Tuple, List

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from .schemas import ConfigSetRequest, ConfigItem, ConfigList
from ..application.handlers import handle_set_config, get_config, list_configs

# Canonical DI for auth + DB
from src.shared.security import get_principal, Principal
from src.dependencies import get_session as get_db_session

router = APIRouter(prefix="/api/v1/config", tags=["Platform Config"])
log = logging.getLogger("platform.config")


@router.get("/{key}", response_model=ConfigItem)
async def get_config_item(
    key: str,
    principal: Optional[Principal] = Depends(get_principal),
    session: AsyncSession = Depends(get_db_session),
):
    if principal is None:
        raise HTTPException(status_code=401, detail="Authentication required")

    tenant_id = principal["tenant_id"]
    row: Optional[Tuple[str, str]] = await get_config(session, tenant_id, key)
    if not row:
        raise HTTPException(status_code=404, detail="Configuration key not found")

    k, v = row
    log.info("config.get", extra={"tenant_id": tenant_id, "key": key})
    return ConfigItem(key=k, value=v)


@router.put("/{key}", response_model=ConfigItem)
async def put_config_item(
    key: str,
    payload: ConfigSetRequest,
    principal: Optional[Principal] = Depends(get_principal),
    session: AsyncSession = Depends(get_db_session),
):
    if principal is None:
        raise HTTPException(status_code=401, detail="Authentication required")

    if payload.key != key:
        # Keep path parameter authoritative to avoid accidental mismatch
        raise HTTPException(status_code=400, detail="Key mismatch between path and body")

    tenant_id = principal["tenant_id"]
    k, v = await handle_set_config(session, tenant_id, key, payload.value)
    log.info("config.upsert", extra={"tenant_id": tenant_id, "key": key})
    return ConfigItem(key=k, value=v)


@router.get("", response_model=ConfigList)
async def list_config_items(
    principal: Optional[Principal] = Depends(get_principal),
    session: AsyncSession = Depends(get_db_session),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    if principal is None:
        raise HTTPException(status_code=401, detail="Authentication required")

    tenant_id = principal["tenant_id"]
    rows: List[Tuple[str, str]] = await list_configs(session, tenant_id, limit, offset)
    log.info("config.list", extra={"tenant_id": tenant_id, "limit": limit, "offset": offset})
    return ConfigList(items=[ConfigItem(key=k, value=v) for k, v in rows])

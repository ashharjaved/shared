from __future__ import annotations

from typing import Any, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, status, Request
from sqlalchemy.ext.asyncio import AsyncSession

from .schemas import (
    SetConfigRequest,
    ConfigResponse,
    ListConfigsResponse,
    ErrorResponse,
)
from ..application.commands import SetConfigCommand, DeleteConfigCommand
from ..domain.entities import TenantConfigView
from ..domain.services import ConfigurationService
from src.platform.infrastructure.Repositories import config_repository
from src.platform.infrastructure.cache import ConfigCache

# DI & utilities imported from shared app deps (appended in src/dependencies.py)
from src.dependencies import (
    get_db_session,
    get_current_tenant,
    get_redis,
    get_settings,
    provide_configuration_service,
    rate_limit_dependency,
)

router = APIRouter()


# ---------- Helpers ----------

def to_response(view: TenantConfigView) -> ConfigResponse:
    return ConfigResponse(
        config_key=view.config_key,
        config_value=view.config_value,
        config_type=view.config_type,
        is_encrypted=view.is_encrypted,
        source_level=view.source_level.value,
        updated_at=view.updated_at,
    )


def error_json(code: str, message: str, details: Optional[dict] = None) -> dict:
    return {"code": code, "message": message, "details": details or {}}


# ---------- Routes ----------

@router.post(
    "/config",
    response_model=ConfigResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        201: {"description": "Created/Updated"},
        400: {"model": ErrorResponse, "description": "validation_error"},
        401: {"model": ErrorResponse, "description": "unauthorized"},
        403: {"model": ErrorResponse, "description": "forbidden"},
        409: {"model": ErrorResponse, "description": "conflict"},
        422: {"model": ErrorResponse, "description": "invalid_request"},
        429: {"model": ErrorResponse, "description": "rate_limited"},
        500: {"model": ErrorResponse, "description": "internal_error"},
    },
)
async def create_or_update_config(
    payload: SetConfigRequest,
    session: AsyncSession = Depends(get_db_session),
    tenant_id: UUID = Depends(get_current_tenant),
    limiter_ok: None = Depends(rate_limit_dependency("POST:/platform/config")),
    service: ConfigurationService = Depends(provide_configuration_service),
):
    """
    Upsert config for the *current tenant* (RLS enforced by GUCs set in session).
    """
    try:
        view = await service.set_config(
            session=session,
            dto=SetConfigCommand(
                tenant_id=tenant_id,
                config_key=payload.config_key,
                config_value=payload.config_value,
                config_type=payload.config_type,
                is_encrypted=payload.is_encrypted,
            ),
        )
        return to_response(view)
    except PermissionError as e:
        # RLS context missing / forbidden
        from fastapi import HTTPException
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=error_json("forbidden", str(e)),
        )
    except Exception as e:
        from fastapi import HTTPException
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=error_json("internal_error", "Unexpected error", {"reason": str(e)}),
        )


@router.get(
    "/config/{key}",
    response_model=ConfigResponse,
    responses={
        200: {"description": "Resolved config (hierarchical; redacted if encrypted)"},
        401: {"model": ErrorResponse},
        403: {"model": ErrorResponse},
        404: {"model": ErrorResponse, "description": "not_found"},
        429: {"model": ErrorResponse},
        500: {"model": ErrorResponse},
    },
)
async def get_config_by_key(
    key: str,
    session: AsyncSession = Depends(get_db_session),
    tenant_id: UUID = Depends(get_current_tenant),
    limiter_ok: None = Depends(rate_limit_dependency("GET:/platform/config/{key}")),
    service: ConfigurationService = Depends(provide_configuration_service),
):
    try:
        view = await service.get_config_resolved(session=session, tenant_id=tenant_id, key=key)
        if view is None:
            from fastapi import HTTPException
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=error_json("not_found", "Config not found", {"key": key}),
            )
        return to_response(view)
    except PermissionError as e:
        from fastapi import HTTPException
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=error_json("forbidden", str(e)),
        )
    except Exception as e:
        from fastapi import HTTPException
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=error_json("internal_error", "Unexpected error", {"reason": str(e)}),
        )


@router.get(
    "/config",
    response_model=ListConfigsResponse,
    responses={
        200: {"description": "List current-tenant configs (no hierarchy)"},
        401: {"model": ErrorResponse},
        403: {"model": ErrorResponse},
        429: {"model": ErrorResponse},
        500: {"model": ErrorResponse},
    },
)
async def list_configs_current_tenant(
    session: AsyncSession = Depends(get_db_session),
    tenant_id: UUID = Depends(get_current_tenant),
    limiter_ok: None = Depends(rate_limit_dependency("GET:/platform/config")),
    service: ConfigurationService = Depends(provide_configuration_service),
):
    try:
        items = await service.list_configs_current_tenant(session=session, tenant_id=tenant_id)
        return ListConfigsResponse(items=[to_response(it) for it in items])
    except PermissionError as e:
        from fastapi import HTTPException
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=error_json("forbidden", str(e)),
        )
    except Exception as e:
        from fastapi import HTTPException
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=error_json("internal_error", "Unexpected error", {"reason": str(e)}),
        )


@router.delete(
    "/config/{key}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={
        204: {"description": "Deleted"},
        401: {"model": ErrorResponse},
        403: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
        429: {"model": ErrorResponse},
        500: {"model": ErrorResponse},
    },
)
async def delete_config(
    key: str,
    session: AsyncSession = Depends(get_db_session),
    tenant_id: UUID = Depends(get_current_tenant),
    limiter_ok: None = Depends(rate_limit_dependency("DELETE:/platform/config/{key}")),
    service: ConfigurationService = Depends(provide_configuration_service),
):
    try:
        # If it doesn't exist, repo delete is no-op; we return 204 to keep idempotent semantics
        await service.delete_config(
            session=session,
            dto=DeleteConfigCommand(tenant_id=tenant_id, config_key=key),
        )
        return None
    except PermissionError as e:
        from fastapi import HTTPException
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=error_json("forbidden", str(e)),
        )
    except Exception as e:
        from fastapi import HTTPException
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=error_json("internal_error", "Unexpected error", {"reason": str(e)}),
        )

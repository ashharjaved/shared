from __future__ import annotations

import logging
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, status
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import get_settings
from src.identity.application.commands import BootstrapPlatform, CreateUser
from src.identity.application.handlers import IdentityHandlers
from src.identity.api.schemas import (
    AdminCreateUserRequest,
    AdminCreateUserResponse,
    BootstrapRequest,
    BootstrapResponse,
    ChangePasswordRequest,
    LoginRequest,
    LoginResponse,
    MeResponse,
    SuccessResponse,
)
from src.identity.domain.services import AuthenticationService
from src.identity.infrastructure.Repositories import TenantRepository, UserRepository
from src.dependencies import get_db_session, get_db 
from src.shared.database import set_rls_gucs
from src.shared.exceptions import UnauthorizedError
from src.shared.security import Role, require_auth, require_roles, get_password_hasher, get_token_provider

logger = logging.getLogger("app.api")

auth_router = APIRouter(prefix="/api/v1/auth", tags=["Identity"])
admin_router = APIRouter(prefix="/api/v1/admin", tags=["Identity"])

# ----------------------------- DB HEALTH CHECK ------------------------------ #
# Lives under /api/v1/admin to avoid adding a new router; no auth required.
@admin_router.get(
    "/health/db",
    summary="Database connectivity health check",
    responses={200: {"description": "DB reachable"}},
)
async def db_health(db: AsyncSession = Depends(get_db)):
    """
    Verifies database connectivity by executing simple, read-only statements.
    Does NOT require JWT. Useful for probes and quick troubleshooting.
    """
    # Basic ping
    one = (await db.execute(text("SELECT 1"))).scalar_one()

    # A few extra diagnostics
    server_version = (await db.execute(text("SHOW server_version"))).scalar_one()
    current_db = (await db.execute(text("SELECT current_database()"))).scalar_one()
    now_utc = (await db.execute(text("SELECT now() AT TIME ZONE 'UTC'"))).scalar_one()

    return {
        "status": "ok" if one == 1 else "bad",
        "server_version": str(server_version),
        "database": str(current_db),
        "time_utc": str(now_utc),
    }
# --------------------------------------------------------------------------- #

@admin_router.post(
    "/bootstrap",
    response_model=BootstrapResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        201: {"description": "Bootstrap successful"},
        401: {"description": "Unauthorized"},
        403: {"description": "Forbidden"},
        409: {"description": "Conflict"},
        429: {"description": "Rate limit exceeded"},
        500: {"description": "Internal error"},
    },
)
async def bootstrap_platform(
    # Use raw DB dependency because bootstrap occurs before a JWT is available
    payload: BootstrapRequest,
    db: AsyncSession = Depends(get_db),
    bootstrap_token: Annotated[str | None, Header(alias="X-Bootstrap-Token")] = None,
):
    settings = get_settings()
    if not bootstrap_token or bootstrap_token != settings.BOOTSTRAP_TOKEN:
        raise UnauthorizedError("Invalid bootstrap token")

    handlers = IdentityHandlers(db)
    result = await handlers.bootstrap(BootstrapPlatform(**payload.model_dump()))
    return BootstrapResponse(**result)

@admin_router.post(
    "/users",
    response_model=AdminCreateUserResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        201: {"description": "User created"},
        401: {"description": "Unauthorized"},
        403: {"description": "Forbidden"},
        409: {"description": "Conflict (email exists)"},
        429: {"description": "Rate limit exceeded"},
    },
    dependencies=[Depends(require_roles(Role.SUPER_ADMIN, Role.RESELLER_ADMIN, Role.TENANT_ADMIN))],
)
async def admin_create_user(
    # Use RLS-aware DB dependency because user creation requires an authenticated tenant context
    payload: AdminCreateUserRequest,
    jwt_claims=Depends(require_auth),
    db: AsyncSession = Depends(get_db_session),
):
    # RLS is already applied by get_db_session; create the user via the handler
    handlers = IdentityHandlers(db)
    result = await handlers.admin_create_user(tenant_id=UUID(jwt_claims["tenant_id"]), cmd=CreateUser(**payload.model_dump()))
    return AdminCreateUserResponse(**result)


@auth_router.post(
    "/login",
    response_model=LoginResponse,
    responses={
        200: {"description": "Login successful"},
        401: {"description": "Invalid credentials"},
        404: {"description": "Tenant not found"},
        429: {"description": "Account locked (too many attempts)"},
    },
)
async def login(
    payload: LoginRequest,
    # Use raw DB dependency because login occurs before a JWT is available
    db: AsyncSession = Depends(get_db),
):
    tenants = TenantRepository(db)
    tenant = await tenants.get_by_name(payload.tenant_name)
    if tenant:
        # Set RLS in a transaction so SET LOCAL persists for subsequent queries
        async with db.begin():
            await set_rls_gucs(db, tenant_id=str(tenant.id), user_id=None, roles=None)

    # Wire abstractions for the service
    hasher = get_password_hasher()
    tokens = get_token_provider()
    service = AuthenticationService(UserRepository(db), tenants, hasher, tokens)
    token, _ = await service.login(payload.tenant_name, payload.email, payload.password)
    return LoginResponse(access_token=token)


@auth_router.get(
    "/me",
    response_model=MeResponse,
    responses={
        200: {"description": "Current user"},
        401: {"description": "Unauthorized"},
        429: {"description": "Rate limit exceeded"},
    },
)

async def me(jwt_claims=Depends(require_auth), db: AsyncSession = Depends(get_db_session)):
    await set_rls_gucs(db, tenant_id = jwt_claims["tenant_id"], user_id=jwt_claims["sub"], roles=jwt_claims["role"])
    user = await UserRepository(db).get_by_id(UUID(jwt_claims["sub"]))
    if not user:
        raise UnauthorizedError("User not found")
    return MeResponse(
        id=user.id,
        tenant_id=user.tenant_id,
        email=user.email,
        role=Role(user.role),
        is_active=user.is_active,
        is_verified=user.is_verified,
    )

@auth_router.post(
    "/password/change",
    response_model=SuccessResponse,
    responses={
        200: {"description": "Password changed"},
        401: {"description": "Unauthorized"},
        429: {"description": "Rate limit exceeded"},
    },
)

async def change_password(payload: ChangePasswordRequest, jwt_claims=Depends(require_auth), db: AsyncSession = Depends(get_db_session)):
    await set_rls_gucs(db, tenant_id=jwt_claims["tenant_id"], user_id=jwt_claims["sub"], roles=jwt_claims["role"])
    repo = UserRepository(db)
    user = await repo.get_by_id(UUID(jwt_claims["sub"]))
    if not user:
        raise UnauthorizedError("User not found")

    hasher = get_password_hasher()
    tokens = get_token_provider()
    service = AuthenticationService(repo, TenantRepository(db), hasher, tokens)
    await service.change_password(user, payload.old_password, payload.new_password)
    return SuccessResponse()


@auth_router.post(
    "/logout",
    response_model=SuccessResponse,
    responses={200: {"description": "Stateless logout (client should discard token)"}},
)
async def logout() -> SuccessResponse:
    return SuccessResponse()
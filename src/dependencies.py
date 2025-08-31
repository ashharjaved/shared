# src/dependencies.py
from __future__ import annotations

import os
from typing import AsyncGenerator, Optional

from fastapi import Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy import text

from src.shared.exceptions import UnauthorizedError
from src.shared.roles import Role, has_min_role
from src.shared.error_codes import ERROR_CODES


# --- DB engine / session factory ---
DB_URL = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./dev.db")
engine = create_async_engine(DB_URL, echo=False, pool_pre_ping=True)
SessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def _set_rls_gucs(session: AsyncSession, *, tenant_id: Optional[str], user_id: Optional[str], role: Optional[str]) -> None:
    """
    Best-effort RLS GUC application.
    Uses 'SET' (not LOCAL) and resets in finally to avoid transaction coupling.
    On non-Postgres (e.g., SQLite), this is a no-op.
    """
    if not tenant_id:
        # Caller may still perform public tables ops, but our services typically enforce RLS presence.
        return
    try:
        await session.execute(text("SELECT set_config('app.jwt_tenant', :v, true)"), {"v": str(tenant_id)})
        if user_id:
            await session.execute(text("SELECT set_config('app.jwt_user', :v, true)"), {"v": str(user_id)})
        if role:
            await session.execute(text("SELECT set_config('app.jwt_roles', :v, true)"), {"v": str(role)})
    except Exception:
        # DB may not support GUCs (e.g., SQLite). Ignore.
        pass


async def _reset_rls_gucs(session: AsyncSession) -> None:
    try:
        await session.execute(text("RESET app.jwt_tenant"))
        await session.execute(text("RESET app.jwt_user"))
        await session.execute(text("RESET app.jwt_roles"))
    except Exception:
        pass


async def get_db_session(request: Request) -> AsyncGenerator[AsyncSession, None]:
    """
    Provides an AsyncSession and applies per-request GUCs from JWT claims
    (set by JwtContextMiddleware) before yielding. Resets on exit.
    """
    session: AsyncSession = SessionLocal()
    claims = getattr(request.state, "user_claims", {}) or {}
    tenant_id = claims.get("tenant_id")
    user_id = claims.get("sub")
    role = claims.get("role")

    await _set_rls_gucs(session, tenant_id=tenant_id, user_id=user_id, role=role)
    try:
        yield session
    finally:
        await _reset_rls_gucs(session)
        await session.close()


# --- Repository constructors (adjust import paths if your repos live elsewhere) ---
def get_user_repo(session: AsyncSession = Depends(get_db_session)):
    # Example expected protocol: find_by_email, get_by_id, create, change_role, deactivate, reactivate, exists_by_email_in_tenant, ...
    from src.identity.infrastructure.user_repository_impl import UserRepository  # type: ignore
    return UserRepository(session)


def get_tenant_repo(session: AsyncSession = Depends(get_db_session)):
    from src.identity.infrastructure.tenant_repository_impl import TenantRepository  # type: ignore
    return TenantRepository(session)

def require_role(required_role: Role):
    """
    FastAPI dependency generator that enforces the current_user
    has at least the given role.

    Usage:
        @router.post("/create", dependencies=[Depends(require_role(Role.TENANT_ADMIN))])
    """
    def _enforce(current_user = Depends(get_current_user)):
        if not has_min_role(current_user.role, required_role):
            data = ERROR_CODES["forbidden"]
            raise UnauthorizedError(
                data["message"],
                code="forbidden",
                status_code=data["http"]
            )
        return current_user

    return _enforce

# --- Current user & role guard ---
async def get_current_user(
    request: Request,
    user_repo=Depends(get_user_repo),
):
    claims = getattr(request.state, "user_claims", None)
    if not claims:
        data = ERROR_CODES["invalid_credentials"]
        raise HTTPException(status_code=data["http"], detail={"code": "invalid_credentials", "message": data["message"]})
    user_id = claims.get("sub")
    user = await user_repo.get_by_id(user_id) if callable(getattr(user_repo, "get_by_id", None)) else user_repo.get_by_id(user_id)
    if not user:
        data = ERROR_CODES["user_not_found"]
        raise HTTPException(status_code=data["http"], detail={"code": "user_not_found", "message": data["message"]})
    return user


# --- JWT parsing middleware helper (used in main.py) ---
def extract_bearer_token(request: Request) -> Optional[str]:
    auth = request.headers.get("Authorization", "")
    if not auth.lower().startswith("bearer "):
        return None
    return auth.split(" ", 1)[1].strip()

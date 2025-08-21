from __future__ import annotations
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional
from sqlalchemy import text
from fastapi import Header
from jose import jwt
from src.config import settings
import debugpy
from .schemas import (
    TenantCreate, TenantRead, TenantUpdate, TenantStatusUpdate,
    UserCreate, UserRead, TokenRequest, TokenResponse
)
from ..application.commands import (
    CreateTenant, CreateUser, AssignRole,
    UpdateTenant, UpdateTenantStatus
)

from ..application.handlers import (
    handle_create_tenant, handle_create_user,
    handle_assign_role, verify_password, handle_update_tenant, handle_update_tenant_status
)
from src.shared.security import create_access_token, require_roles, get_principal, get_tenant_from_header
from src.shared.database import get_session
from src.identity.infrastructure.repositories import TenantRepository, UserRepository
from src.identity.domain.entities import Principal
router = APIRouter(prefix="/api/v1/auth", tags=["Identity"])

# ---- Tenants (platform scoped) ----
@router.post("/tenants", response_model=TenantRead, status_code=status.HTTP_201_CREATED,
             dependencies=[Depends(require_roles("SUPER_ADMIN"))])
async def create_tenant(payload: TenantCreate, session: AsyncSession = Depends(get_session)):
    repo = TenantRepository(session)
    t = await handle_create_tenant(CreateTenant(**payload.dict()), repo)
    await session.commit()
    return TenantRead(
        id=t.id, name=t.name, tenant_type=t.tenant_type,
        subscription_status=t.subscription_status, is_active=t.is_active
    )


@router.get("/tenants", response_model=List[TenantRead], dependencies=[Depends(require_roles("SUPER_ADMIN"))])
async def list_tenants(session: AsyncSession = Depends(get_session)):
    """List all tenants, including inactive ones."""
    # Note: This is for platform owners only, so we don't filter by tenant_id
    repo = TenantRepository(session)
    rows = await repo.list(active_only=False)
    return [TenantRead(id=t.id, name=t.name, tenant_type=t.tenant_type,
                       subscription_status=t.subscription_status, is_active=t.is_active) for t in rows]

# NEW: update tenant fields
@router.patch("/tenants/{tenant_id}", response_model=TenantRead,
              dependencies=[Depends(require_roles("PLATFORM_OWNER","SUPER_ADMIN"))])
async def update_tenant(tenant_id: UUID, payload: TenantUpdate, session: AsyncSession = Depends(get_session)):
    repo = TenantRepository(session)
    t = await handle_update_tenant(UpdateTenant(tenant_id=tenant_id, **payload.dict()), repo)
    if not t:
        raise HTTPException(status_code=404, detail="Tenant not found")
    await session.commit()
    return TenantRead(
        id=t.id, name=t.name, tenant_type=t.tenant_type,
        subscription_status=t.subscription_status, is_active=t.is_active
    )

# Existing status-by-path (kept for backward compat)
@router.post("/tenants/{tenant_id}/status/{status}", dependencies=[Depends(require_roles("SUPER_ADMIN"))])
async def set_tenant_status(tenant_id: UUID, status: str, session: AsyncSession = Depends(get_session)):
    repo = TenantRepository(session)
    if status not in {"activate", "deactivate"}:
        raise HTTPException(status_code=400, detail="status must be 'activate' or 'deactivate'")
    ok = await repo.set_status(tenant_id, is_active=(status == "activate"))
    await session.commit()
    if not ok:
        raise HTTPException(status_code=404, detail="Tenant not found")
    return {"ok": True}

# NEW: status update via body (supports is_active and/or subscription_status)
@router.patch("/tenants/{tenant_id}/status",
              dependencies=[Depends(require_roles("PLATFORM_OWNER", "RESELLER"))])
async def patch_tenant_status(tenant_id: UUID, payload: TenantStatusUpdate, session: AsyncSession = Depends(get_session)):
    if payload.is_active is None and payload.subscription_status is None:
        raise HTTPException(status_code=400, detail="Provide is_active and/or subscription_status")
    repo = TenantRepository(session)
    t = await handle_update_tenant_status(UpdateTenantStatus(
        tenant_id=tenant_id,
        is_active=payload.is_active,
        subscription_status=payload.subscription_status
    ), repo)
    if not t:
        raise HTTPException(status_code=404, detail="Tenant not found")
    await session.commit()
    return {
        "ok": True,
        "tenant": {
            "id": t.id,
            "is_active": t.is_active,
            "subscription_status": t.subscription_status
        }
    }

# ---- JWT (bootstrap allows X-Tenant-Id) ----
@router.post("/token", response_model=TokenResponse)
async def issue_token(
    payload: TokenRequest,
    session: AsyncSession = Depends(get_session),
    tenant_hint: Optional[UUID] = Depends(get_tenant_from_header),
):
    if not tenant_hint:
        raise HTTPException(status_code=400, detail="X-Tenant-Id header required for login")
    user_repo = UserRepository(session)
    user = await user_repo.by_email(tenant_hint, payload.email)
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    token = create_access_token(
        subject=user.email,
        tenant_id=user.tenant_id,
        role=[user.role]  # ensure simple list[str]
    )
    return TokenResponse(access_token=token, expires_in=settings.JWT_EXPIRE_MIN * 60)
    

# ---- Users (tenant scoped; admin only) ----
@router.post("/users", response_model=UserRead, status_code=status.HTTP_201_CREATED)
async def create_user(
    payload: UserCreate,
    principal: Principal = Depends(require_roles("SUPER_ADMIN", "RESELLER", "TENANT_ADMIN")),
    session: AsyncSession = Depends(get_session),
):
    debugpy.breakpoint()
    # Determine target tenant for creation:
    # - SUPER_ADMIN / RESELLER: can set payload.tenant_id (must be provided).
    # - Others (e.g., TENANT_ADMIN): default to caller's tenant if not provided; cross-tenant disallowed.
    is_privileged = bool({"SUPER_ADMIN", "RESELLER"} & principal.role)
    target_tenant_id = payload.tenant_id or principal.tenant_id

    if not is_privileged and payload.tenant_id and payload.tenant_id != principal.tenant_id:
        raise HTTPException(status_code=403, detail="Cross-tenant user creation is not allowed")
    if is_privileged and not target_tenant_id:
        # For privileged callers, tenant_id must be explicit (they may not belong to the target tenant)
        raise HTTPException(status_code=400, detail="tenant_id is required for privileged user creation")


    user_repo = UserRepository(session)
    u = await handle_create_user(
        CreateUser(
            tenant_id=target_tenant_id,
            email=payload.email,
            password=payload.password,
            role=payload.role,
        ),
        user_repo,
    )
    await session.commit()
    return UserRead(id=u.id, tenant_id=u.tenant_id, email=u.email, role=u.role, is_active=u.is_active, is_verified=u.is_verified)

@router.get("/users/{user_id}", response_model=UserRead)
async def get_user(
    user_id: UUID,
    principal: Principal = Depends(require_roles("STAFF", "PLATFORM_OWNER", "RESELLER","SUPER_ADMIN")),
    session: AsyncSession = Depends(get_session),
):
    user_repo = UserRepository(session)
    u = await user_repo.by_id(principal.tenant_id, user_id)
    if not u:
        raise HTTPException(status_code=404, detail="User not found")
    if principal.user_id != u.id and not principal.has_any_role("SUPER-ADMIN", "RESELLER"):
        raise HTTPException(status_code=403, detail="Forbidden")
    return UserRead(id=u.id, tenant_id=u.tenant_id, email=u.email, role=u.role, is_active=u.is_active, is_verified=u.is_verified)

@router.post("/users/{user_id}/roles", dependencies=[Depends(require_roles("PLATFORM_OWNER", "RESELLER","SUPER_ADMIN"))])
async def assign_user_roles(
    user_id: str,
    roles: List[str],
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_session),
):
    user_repo = UserRepository(session)
    # Assign one by one to reuse existing handler; keep idempotency
    u = None
    for r in roles:
        u = await handle_assign_role(AssignRole(tenant_id=principal.tenant_id, user_id=user_id, role=r), user_repo)
    await session.commit()
    if not u:
        raise HTTPException(status_code=404, detail="User not found")
    return {"ok": True, "roles": u.role}

@router.get("/whoami")
async def whoami(
    authorization: str = Header(None),
    session: AsyncSession = Depends(get_session),
):
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Missing Bearer token")
    token = authorization.split(" ", 1)[1].strip()

    # Decode token using app secret
    raw = settings.JWT_SECRET
    secret = raw.get_secret_value() if hasattr(raw, "get_secret_value") else (raw if isinstance(raw, str) else "")
    alg = getattr(settings, "JWT_ALG", "HS256")
    claims = jwt.decode(token, secret, algorithms=[alg])

    tid = str(claims.get("tenant_id") or "").strip()
    sub = str(claims.get("email") or claims.get("preferred_username") or claims.get("sub") or "").strip()
    roles = claims.get("roles") or []
    if not isinstance(roles, list):
        roles = [str(roles)]
    if not tid:
        raise HTTPException(status_code=400, detail="token missing tenant_id")

    # Bind tenant for this request
    await session.execute(text("SELECT set_config('app.jwt_tenant', :tid, true)"), {"tid": tid})

    # Resolve user by email (CITEXT, TRIM) OR id-as-sub
    res = await session.execute(
        text("""
            WITH c AS (
              SELECT id::text AS id, trim(email::text) AS e
              FROM users
              WHERE tenant_id = :tid
            )
            SELECT id
            FROM c
            WHERE e::citext = trim(:sub)::citext
               OR id = :sub
            LIMIT 1
        """),
        {"tid": tid, "sub": sub},
    )
    user_id = res.scalar_one_or_none()

    return {"user_id": user_id, "tenant_id": tid, "email": sub or None, "roles": roles}

@router.get("/_trace/whoami")
async def trace_whoami(
    authorization: str = Header(None),
    session: AsyncSession = Depends(get_session),
):
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Missing Bearer token")
    token = authorization.split(" ", 1)[1].strip()

    try:
        raw = settings.JWT_SECRET
        secret = raw.get_secret_value() if hasattr(raw, "get_secret_value") else (raw if isinstance(raw, str) else "")
        alg = getattr(settings, "JWT_ALG", "HS256")
        claims = jwt.decode(token, secret, algorithms=[alg])
        tid = str(claims.get("tenant_id") or "").strip()
        sub = str(claims.get("email") or claims.get("preferred_username") or claims.get("sub") or "").strip()
        if not tid:
            raise HTTPException(status_code=400, detail="token missing tenant_id")

        await session.execute(text("SELECT set_config('app.jwt_tenant', :tid, true)"), {"tid": tid})

        res = await session.execute(
            text("""
                SELECT
                  id::text                         AS id,
                  email::text                      AS email,
                  trim(email::text)                AS email_trim,
                  (trim(email::text)::citext = trim(:sub)::citext) AS eq_citext_trim,
                  (email = :sub)                   AS eq_text,
                  (lower(email) = lower(:sub))     AS eq_lower,
                  (id::text = :sub)                AS eq_id
                FROM users
                WHERE tenant_id = :tid
                ORDER BY 1 DESC
                LIMIT 5
            """),
            {"tid": tid, "sub": sub},
        )
        rows = [dict(m) for m in res.mappings().all()]
        return {"tenant_from_token": tid, "sub_used": sub, "rows": rows}
    except Exception as e:
        # Surface exact error so it never 500s silently
        raise HTTPException(status_code=500, detail=f"{type(e).__name__}: {e}")

@router.get("/whoami_db")
async def whoami_db(
    authorization: str = Header(None),
    session: AsyncSession = Depends(get_session),
):
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Missing Bearer token")
    token = authorization.split(" ", 1)[1].strip()

    # Decode token using app secret
    raw = settings.JWT_SECRET
    secret = raw.get_secret_value() if hasattr(raw, "get_secret_value") else (raw if isinstance(raw, str) else "")
    alg = getattr(settings, "JWT_ALG", "HS256")
    claims = jwt.decode(token, secret, algorithms=[alg])

    tid = str(claims.get("tenant_id") or "").strip()
    sub = str(claims.get("email") or claims.get("preferred_username") or claims.get("sub") or "").strip()
    role = claims.get("roles")
    if not isinstance(role, list):
        role = [str(role)]
    if not tid:
        raise HTTPException(status_code=400, detail="token missing tenant_id")

    # Bind tenant (parameter-safe)
    await session.execute(text("SELECT set_config('app.jwt_tenant', :tid, true)"), {"tid": tid})

    # Resolve user by CITEXT email OR id-as-sub (trimmed)
    res = await session.execute(
        text("""
            WITH c AS (
              SELECT id::text AS id, trim(email::text)::citext AS e
              FROM users
              WHERE tenant_id = :tid
            )
            SELECT id
            FROM c
            WHERE e = trim(:sub)::citext
               OR id = :sub
            LIMIT 1
        """),
        {"tid": tid, "sub": sub},
    )
    user_id = res.scalar_one_or_none()

    return {"user_id": user_id, "tenant_id": tid, "email": sub or None, "role": role}


@router.get("/_debug/whoami")
async def debug_whoami(
    principal: Principal | None = Depends(get_principal),
    session: AsyncSession = Depends(get_session),
):
    if principal is None:
        raise HTTPException(status_code=401, detail="Missing/invalid token")

    try:
        await session.execute(
            text("SELECT set_config('app.jwt_tenant', :tid, true)"),
            {"tid": str(principal.tenant_id)},
        )

    except Exception:
        pass

    res = await session.execute(
        text("""
            SELECT
              current_database()                          AS db,
              current_setting('app.jwt_tenant', true)     AS tenant_guc,
              (SELECT count(*) FROM users)                AS users_total,
              (SELECT count(*) FROM users WHERE tenant_id = :tid) AS users_in_tenant
        """),
        {"tid": str(principal.tenant_id)},
    )
    m = res.mappings().first()
    if m is None:
        raise HTTPException(status_code=404, detail="No debug info found for tenant")
    return {
        "db": m["db"],
        "tenant_guc": m["tenant_guc"],
        "principal_sub": getattr(principal, "email", None) or getattr(principal, "sub", None),
        "principal_tenant": str(principal.tenant_id),
        "users_total": int(m["users_total"]),
        "users_in_tenant": int(m["users_in_tenant"]),
    }

@router.get("/_raw")
async def debug_raw_token(authorization: str = Header(None)):
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Missing Bearer token")
    token = authorization.split(" ", 1)[1].strip()

    # 1) Show unverified claims (helps even if secret/alg mismatched)
    try:
        unverified = jwt.get_unverified_claims(token)
    except Exception as e:
        unverified = {"_error": f"unverified decode failed: {type(e).__name__}: {e}"}

    # 2) Try verified decode with your configured secret/alg
    try:
        raw = settings.JWT_SECRET
        secret = raw.get_secret_value() if hasattr(raw, "get_secret_value") else (raw if isinstance(raw, str) else "")
        alg = getattr(settings, "JWT_ALG", "HS256")
        verified = jwt.decode(token, secret, algorithms=[alg])
    except Exception as e:
        verified = {"_error": f"verified decode failed: {type(e).__name__}: {e}"}

    return {"unverified": unverified, "verified": verified}

@router.get("/_probe")
async def debug_probe(
    authorization: str = Header(None),
    session: AsyncSession = Depends(get_session),
):
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Missing Bearer token")
    token = authorization.split(" ", 1)[1].strip()

    try:
        raw = settings.JWT_SECRET
        secret = raw.get_secret_value() if hasattr(raw, "get_secret_value") else (raw if isinstance(raw, str) else "")
        alg = getattr(settings, "JWT_ALG", "HS256")
        claims = jwt.decode(token, secret, algorithms=[alg])
    except Exception as e:
        raise HTTPException(status_code=401, detail=f"Token decode failed: {type(e).__name__}: {e}")

    tenant_id = str(claims.get("tenant_id") or "")

    try:
        if tenant_id:
            await session.execute(
                text("SELECT set_config('app.jwt_tenant', :tid, true)"),
                {"tid": str(tenant_id)},)


        res = await session.execute(
            text("SELECT current_database() AS db, current_setting('app.jwt_tenant', true) AS tenant_guc")
        )
        row = res.mappings().first()
        if row is None:
            raise HTTPException(status_code=404, detail="No database info found")
        return {
            "db": row["db"],
            "tenant_guc": row["tenant_guc"],
            "token_tenant": tenant_id or None,
        }
    except Exception as e:
        # TEMP: surface the DB error so we know exactly what's wrong
        raise HTTPException(status_code=500, detail=f"DB error: {type(e).__name__}: {e}")
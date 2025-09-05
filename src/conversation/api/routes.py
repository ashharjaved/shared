#*** Begin: src/conversation/api/routes.py ***
from __future__ import annotations

import logging
from typing import Any, Dict, Optional, Tuple
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status, Query
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from ..domain.entities import MenuFlow
from ..domain.errors import FlowNotFoundError
from ..domain.value_objects import MenuDefinition
from ..infrastructure import (
    PostgresFlowRepository,
    with_rls,
)
from ..infrastructure.models import ConversationSessionORM
from .schemas import (
    MenuFlowCreate,
    MenuFlowUpdate,
    MenuFlowRead,
    SessionRead,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/conversation", tags=["conversation"])


# ---------------------------------------------------------
# Helpers: error contract + DI (session factory, auth claims)
# ---------------------------------------------------------
def _error(http: int, code: str, message: str, details: Optional[Dict[str, Any]] = None) -> HTTPException:
    return HTTPException(status_code=http, detail={"code": code, "message": message, "details": details})

def _extract_claims(request: Request) -> Dict[str, Any]:
    claims = getattr(request.state, "user_claims", None)
    if not claims:
        raise _error(status.HTTP_401_UNAUTHORIZED, "unauthorized", "Missing or invalid credentials")
    return claims

def _claim_tenant_user(claims: Dict[str, Any]) -> Tuple[UUID, Optional[UUID], Optional[str]]:
    # Support multiple claim shapes; normalize to UUIDs/roles_csv
    try:
        tid_raw = claims.get("tenant_id") or claims.get("tid") or claims.get("tenant")
        uid_raw = claims.get("sub") or claims.get("user_id")
        roles_raw = claims.get("roles") or claims.get("role") or ""
        tenant_id = UUID(str(tid_raw))
        user_id = UUID(str(uid_raw)) if uid_raw else None
        roles_csv = ",".join(roles_raw) if isinstance(roles_raw, (list, tuple)) else str(roles_raw)
        return tenant_id, user_id, roles_csv or None
    except Exception:
        raise _error(status.HTTP_401_UNAUTHORIZED, "unauthorized", "Invalid auth claims")

def _get_session_factory() -> async_sessionmaker[AsyncSession]:
    """
    Import your app's session factory. Adjust the import path if needed.
    Must return: async_sessionmaker[AsyncSession]
    """
    try:
        # Common location in this project:
        from src.shared.database import get_session  # type: ignore
        return get_session()
    except Exception:  # pragma: no cover - fallback
        from src.platform.infrastructure.database import get_session  # type: ignore
        return get_session()


def _make_flow_repo(
    *, session_factory: async_sessionmaker[AsyncSession], tenant_id: UUID, user_id: Optional[UUID], roles_csv: Optional[str]
) -> PostgresFlowRepository:
    return PostgresFlowRepository(
        session_factory=session_factory,
        tenant_id=tenant_id,
        user_id=user_id,
        roles_csv=roles_csv,
    )


def _to_read(flow: MenuFlow) -> MenuFlowRead:
    return MenuFlowRead(
        id=flow.id,
        tenant_id=flow.tenant_id,
        name=flow.name,
        industry_type=flow.industry_type,
        version=flow.version,
        is_active=flow.is_active,
        is_default=flow.is_default,
        definition_json=flow.definition.to_json(),
        created_by=flow.created_by,
        created_at=flow.created_at,
        updated_at=flow.updated_at,
    )


# ---------------------------------------------------------
# Routes: Flows
# ---------------------------------------------------------
@router.post("/flows", response_model=MenuFlowRead, status_code=status.HTTP_201_CREATED)
async def create_flow(
    body: MenuFlowCreate,
    request: Request,
) -> MenuFlowRead:
    claims = _extract_claims(request)
    tenant_id, user_id, roles_csv = _claim_tenant_user(claims)
    sf = _get_session_factory()
    repo = _make_flow_repo(session_factory=sf, tenant_id=tenant_id, user_id=user_id, roles_csv=roles_csv)

    flow = MenuFlow(
        id=uuid4(),
        tenant_id=tenant_id,
        name=body.name,
        industry_type=body.industry_type,
        version=body.version,
        is_active=body.is_active,
        is_default=body.is_default,
        definition=MenuDefinition.from_json(body.definition),
        created_by=user_id,
    )
    try:
        saved = await repo.create(flow)
        return _to_read(saved)
    except Exception as e:
        # Likely unique violation (name,version) or partial default uniqueness
        logger.exception("create_flow failed")
        raise _error(status.HTTP_409_CONFLICT, "conflict", "Flow already exists or default constraint violated")


@router.put("/flows/{flow_id}", response_model=MenuFlowRead)
async def update_flow(
    flow_id: UUID,
    body: MenuFlowUpdate,
    request: Request,
) -> MenuFlowRead:
    claims = _extract_claims(request)
    tenant_id, user_id, roles_csv = _claim_tenant_user(claims)
    sf = _get_session_factory()
    repo = _make_flow_repo(session_factory=sf, tenant_id=tenant_id, user_id=user_id, roles_csv=roles_csv)

    try:
        existing = await repo.get_by_id(flow_id)
    except FlowNotFoundError:
        raise _error(status.HTTP_404_NOT_FOUND, "not_found", "Flow not found")

    # Build updated entity (immutability in domain is simple dataclass reassignment)
    updated = MenuFlow(
        id=existing.id,
        tenant_id=existing.tenant_id,
        name=body.name or existing.name,
        industry_type=body.industry_type or existing.industry_type,
        version=body.version if body.version is not None else existing.version,
        is_active=body.is_active if body.is_active is not None else existing.is_active,
        is_default=body.is_default if body.is_default is not None else existing.is_default,
        definition=MenuDefinition.from_json(body.definition) if body.definition is not None else existing.definition,
        created_by=existing.created_by,
        created_at=existing.created_at,
        updated_at=existing.updated_at,
        deleted_at=existing.deleted_at,
    )

    try:
        saved = await repo.update(updated)
        return _to_read(saved)
    except Exception:
        logger.exception("update_flow failed")
        raise _error(status.HTTP_409_CONFLICT, "conflict", "Update violates constraints")


@router.get("/flows", response_model=list[MenuFlowRead])
async def list_flows(
    request: Request,
    active: Optional[bool] = Query(default=None),
    name: Optional[str] = Query(default=None),
    industry: Optional[str] = Query(default=None, alias="industry_type"),
) -> list[MenuFlowRead]:
    claims = _extract_claims(request)
    tenant_id, user_id, roles_csv = _claim_tenant_user(claims)
    sf = _get_session_factory()
    repo = _make_flow_repo(session_factory=sf, tenant_id=tenant_id, user_id=user_id, roles_csv=roles_csv)

    flows = await repo.list(active=active, name=name, industry_type=industry)
    return [_to_read(f) for f in flows]


# ---------------------------------------------------------
# Routes: Sessions (admin/debug)
# ---------------------------------------------------------
@router.get("/sessions", response_model=list[SessionRead])
async def list_active_sessions(
    request: Request,
    channel_id: Optional[UUID] = Query(default=None),
    include_expired: bool = Query(default=False),
    limit: int = Query(default=50, ge=1, le=500),
) -> list[SessionRead]:
    """
    Admin/debug endpoint to see active sessions for the tenant.
    Uses direct ORM under RLS (no PHI in fields).
    """
    claims = _extract_claims(request)
    tenant_id, user_id, roles_csv = _claim_tenant_user(claims)
    sf = _get_session_factory()

    async with sf() as s, with_rls(s, tenant_id=tenant_id, user_id=user_id, roles_csv=roles_csv):
        stmt = select(ConversationSessionORM).where(ConversationSessionORM.tenant_id == tenant_id)
        if not include_expired:
            stmt = stmt.where(ConversationSessionORM.status == text("'ACTIVE'"))
        if channel_id:
            stmt = stmt.where(ConversationSessionORM.channel_id == channel_id)
        stmt = stmt.order_by(ConversationSessionORM.last_activity.desc()).limit(limit)

        rows = (await s.execute(stmt)).scalars().all()

    out: list[SessionRead] = []
    for r in rows:
        out.append(
            SessionRead(
                id=r.id,
                tenant_id=r.tenant_id,
                channel_id=r.channel_id,
                phone_number=r.phone_number,
                current_menu_id=r.current_menu_id,
                status=str(r.status),
                last_activity=r.last_activity,
                expires_at=r.expires_at,
                message_count=r.message_count,
            )
        )
    return out
#*** End: src/conversation/api/routes.py ***

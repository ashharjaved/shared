from __future__ import annotations

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.shared.database import get_db
from src.shared.security import require_auth, require_roles
from src.identity.domain.value_objects import Role

DbSession = AsyncSession

def db_session() -> DbSession:
    # simple alias for DI clarity
    return Depends(get_db)

def auth_dep():
    return Depends(require_auth)

def admin_required():
    return Depends(require_roles(Role.SUPER_ADMIN, Role.RESELLER_ADMIN, Role.TENANT_ADMIN))

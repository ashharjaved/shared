# /src/shared/http/dependencies.py
"""
FastAPI dependencies for accessing request-scoped context.

- request_context(): returns dict with request_id, tenant_id, user_id, roles
- require_tenant(): raises if tenant_id missing (use inside tenant-protected routes)
"""

from __future__ import annotations
from typing import Dict, Union
from dataclasses import dataclass
from fastapi import Depends, Header, HTTPException, Request, status

from ..utils import tenant_ctxvars as ctxvars


def request_context() -> Dict[str, object]:
    """Expose request-scoped context to route handlers."""
    return ctxvars.get_request_context()

@dataclass(frozen=True)
class TenantContext:
    tenant_id: str
    user_id: str | None = None
    roles: Union[str, list[str], None] = None

def get_tenant_ctx(
    request: Request,
    x_active_tenant: str | None = Header(default=None, alias="X-Active-Tenant"),
) -> TenantContext:
    """
    Minimal example:
    - Read tenant from header (or from JWT claims on request.state / middleware).
    - Populate roles/user_id as available.
    """
    # In your real app, prefer pulling from verified JWT on request.state
    tenant_id = x_active_tenant or ctxvars.get_tenant_id() or getattr(request.state, "tenant_id", None)
    if not tenant_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "forbidden", "message": "Active tenant not set"}
        )

    user_id = ctxvars.get_user_id() or getattr(request.state, "user_id", None)
    roles   = ctxvars.get_roles() or None
    return TenantContext(tenant_id=tenant_id, user_id=user_id, roles=roles)

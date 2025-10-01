# src/shared/utils/tenant_ctxvars.py
from __future__ import annotations
from typing import Dict, Optional, List
import contextvars
from src.shared.database.types import TenantContext as DbTenantContext

# Context variables, set once per request by middleware

TENANT_ID_VAR  = contextvars.ContextVar[Optional[str]]("tenant_id", default=None)
USER_ID_VAR    = contextvars.ContextVar[Optional[str]]("user_id", default=None)
ROLES_VAR      = contextvars.ContextVar[List[str]]("roles", default=[])
REQUEST_ID_VAR = contextvars.ContextVar[Optional[str]]("request_id", default=None)

def set_all(*, tenant_id: Optional[str], user_id: Optional[str], roles: List[str] | None, request_id: Optional[str]) -> None:
    TENANT_ID_VAR.set(tenant_id)
    USER_ID_VAR.set(user_id)
    ROLES_VAR.set(roles or [])
    REQUEST_ID_VAR.set(request_id)

def clear_all() -> None:
    TENANT_ID_VAR.set(None)
    USER_ID_VAR.set(None)
    ROLES_VAR.set([])
    REQUEST_ID_VAR.set(None)

def snapshot() -> Dict[str, object]:
    """Return a simple snapshot of the current ctxvars."""
    return {
        "tenant_id": get_tenant_id(),
        "user_id": get_user_id(),
        "roles": get_roles(),
        "request_id": get_request_id(),
    }

# Typed accessors (prefer these in application/infrastructure)
def get_tenant_id() -> Optional[str]:
    return TENANT_ID_VAR.get()

def get_user_id() -> Optional[str]:
    return USER_ID_VAR.get()

def get_roles() -> List[str]:
    # Always return a copy so callers can't accidentally mutate the ctx list
    return list(ROLES_VAR.get() or [])

def get_request_id() -> Optional[str]:
    return REQUEST_ID_VAR.get()

def get_request_context() -> Dict[str, object]:
    """Convenience: ready-to-log context dict."""
    return {
        "request_id": get_request_id() or "",
        "tenant_id": get_tenant_id() or "",
        "user_id": get_user_id() or "",
        "roles": get_roles(),
    }

# -------------------------------------------------------------------
# Context manager for temporary binding
# -------------------------------------------------------------------
from contextlib import contextmanager

@contextmanager
def bind_tenant_ctx(ctx: DbTenantContext):
    """
    Temporarily bind tenant context into ctxvars for the current request/task.
    Example:
        ctx = DbTenantContext(tenant_id="...", user_id=None, roles=["SYSTEM"])
        with bind_tenant_ctx(ctx):
            await some_service()  # UoW will see tenant_id
    """
    tokens = []
    try:
        tokens.append(TENANT_ID_VAR.set(ctx.tenant_id))
        tokens.append(USER_ID_VAR.set(ctx.user_id))
        tokens.append(ROLES_VAR.set(ctx.roles))
        yield
    finally:
        for tok in reversed(tokens):
            tok.var.reset(tok)
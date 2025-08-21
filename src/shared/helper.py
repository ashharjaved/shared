# --- helpers: normalization + implications ---------------------------------
from typing import Iterable

from src.identity.domain.entities import Principal
from src.shared.security import get_principal

def _normalize_roles(v) -> set[str]:
    """
    Accepts: list/tuple/set, space/comma-separated string, or None.
    Returns: UPPERCASE set[str]
    """
    if not v:
        return set()
    if isinstance(v, str):
        # allow comma or whitespace separated
        parts = [p for chunk in v.split(",") for p in chunk.split()]
        return {p.strip().upper() for p in parts if p.strip()}
    if isinstance(v, Iterable):
        return {str(x).strip().upper() for x in v if str(x).strip()}
    return set()

# Role implication graph (customize for your platform)
ROLE_IMPLIES: dict[str, set[str]] = {
    "SUPERADMIN": {"PLATFORM_OWNER", "RESELLER_ADMIN", "CLIENT_ADMIN", "ADMIN", "USER"},
    "PLATFORM_OWNER": {"ADMIN", "USER"},
    "RESELLER_ADMIN": {"ADMIN", "USER"},
    "CLIENT_ADMIN": {"ADMIN", "USER"},
    "ADMIN": {"USER"},
    "USER": set(),
}

def _closure_with_implications(roles: set[str]) -> set[str]:
    """
    Expand roles with their implied roles.
    """
    expanded = set()
    stack = list(roles)
    while stack:
        r = stack.pop()
        if r in expanded:
            continue
        expanded.add(r)
        for implied in ROLE_IMPLIES.get(r, set()):
            if implied not in expanded:
                stack.append(implied)
    return expanded

# Integrate into principal creation (where you parse JWT claims):
# roles_raw = claims.get("roles") or claims.get("scopes") or claims.get("permissions")
# base_roles = _normalize_roles(roles_raw)
# roles = _closure_with_implications(base_roles)

# And store `roles` on Principal (as a set[str])

# --- require_roles dependency (no DB import to avoid circulars) ------------
from fastapi import Depends, HTTPException

def require_roles(*required: str):
    """
    Enforce RBAC. Accepts one or more required roles; implication is honored.
    """
    required_norm = {r.strip().upper() for r in required if r and r.strip()}

    async def _dep(principal: Principal | None = Depends(get_principal)) -> Principal:
        if principal is None:
            raise HTTPException(status_code=401, detail="Authentication required")

        user_roles = getattr(principal, "roles", set()) or set()
        # If roles on principal aren’t already expanded, expand here defensively:
        effective_roles = _closure_with_implications(_normalize_roles(user_roles))

        # Access if ANY required role is present in effective roles
        if required_norm and required_norm.isdisjoint(effective_roles):
            # Optional: include debugging hint in dev
            # raise HTTPException(status_code=403, detail=f"Insufficient role. Need any of {sorted(required_norm)}, have {sorted(effective_roles)}")
            raise HTTPException(status_code=403, detail="Insufficient role")
        return principal

    return _dep

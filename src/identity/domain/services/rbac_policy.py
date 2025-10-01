# src/shared/security/rbac_policy.py
from __future__ import annotations

from typing import Any, Sequence, Union, overload, Final
from dataclasses import dataclass

# Align with your existing imports (e.g., tenant_service.py uses this path)
from ..value_objects.role import Role, RoleHierarchy  # Enum: SUPER_ADMIN, RESELLER_ADMIN, TENANT_ADMIN, TENANT_USER


# ---- Normalization -----------------------------------------------------------

RoleLike = Union[str, int, Role]
RoleListLike = Union[RoleLike, Sequence[RoleLike]]

def _to_role(value: RoleLike) -> Role:
    """
    Coerce common inputs into a Role enum:
      - Role instance        -> return as-is
      - Name (any case/format): "super_admin", "SUPER-ADMIN", "Super Admin"
      - Numeric (enum value): 0, 1, "0", "1"
      - Fallback: treat small integers as indices into ROLE_ORDER
    """
    if isinstance(value, Role):
        return value

    if isinstance(value, int):
        try:
            # Map integer to RoleHierarchy, then to Role
            hierarchy_role = RoleHierarchy(value)
            return Role[hierarchy_role.name]
        except ValueError:
            # Fallback to ROLE_ORDER index
            if 0 <= value < len(ROLE_ORDER):
                return ROLE_ORDER[value]
            raise TypeError(f"Invalid integer for role: {value!r}")

    if isinstance(value, str):
        s = value.strip()
        # 1) Try name variants
        key = s.upper().replace("-", "_").replace(" ", "_")
        if key in getattr(Role, "__members__", {}):
            return Role[key]
        # 2) Try numeric strings -> enum value or ROLE_ORDER index
        if s.isdigit():
            iv = int(s)
            try:
                # Map numeric string to RoleHierarchy, then to Role
                hierarchy_role = RoleHierarchy(iv)
                return Role[hierarchy_role.name]
            except ValueError:
                if 0 <= iv < len(ROLE_ORDER):
                    return ROLE_ORDER[iv]
                raise TypeError(f"Invalid role string: {value!r}")
        raise TypeError(f"Invalid role string: {value!r}")

def normalize_roles(actor_roles: RoleListLike) -> list[Role]:
    """
    Normalize input (string/int/Role or a sequence of them) to a list[Role].
    Accepts:
      - "SUPER_ADMIN", Role.SUPER_ADMIN, 0, "0"
      - ["TENANT_ADMIN", Role.TENANT_USER, 2]
    Always returns list[Role] (duplicates removed, original order preserved).
    """
    if isinstance(actor_roles, (str, int, Role)):
        roles = [_to_role(actor_roles)]
    else:
        roles = [_to_role(r) for r in actor_roles]

    # Deduplicate while preserving order
    seen: set[Role] = set()
    unique: list[Role] = []
    for r in roles:
        if r not in seen:
            seen.add(r)
            unique.append(r)
    return unique

def _normalize(roles: RoleListLike) -> list[Role]:
    if isinstance(roles, (str, int, Role)):
        items = [_to_role(roles)]
    else:
        items = [_to_role(r) for r in roles]
    seen: set[Role] = set()
    out: list[Role] = []
    for r in items:
        if r not in seen:
            seen.add(r)
            out.append(r)
    return out

# ---- Serialization helpers ---------------------------------------------------

def roles_to_strings(roles: RoleListLike) -> list[str]:
    """Normalize then emit role names for DTOs (e.g., ['SUPER_ADMIN', ...])."""
    return [r.name for r in _normalize(roles)]


# ---- Hierarchy ---------------------------------------------------------------

# Define strict hierarchy (higher index = higher privilege)
# Adjust only here if adding roles later.
ROLE_ORDER: Final[tuple[Role, ...]] = (
    Role.TENANT_USER,
    Role.TENANT_ADMIN,
    Role.RESELLER_ADMIN,
    Role.SUPER_ADMIN,
)

RANK: Final[dict[Role, int]] = {role: idx for idx, role in enumerate(ROLE_ORDER)}

def _rank(role: Role) -> int:
    try:
        return RANK[role]
    except KeyError as e:
        raise ValueError(f"Unknown role in hierarchy: {role}") from e


# ---- Predicates --------------------------------------------------------------

def has_any_role(
    actor_roles: RoleListLike,
    required: RoleListLike,
) -> bool:
    """True if the actor has at least one of the required roles."""
    actor = set(normalize_roles(actor_roles))
    req = set(normalize_roles(required))
    return not actor.isdisjoint(req)

def has_all_roles(
    actor_roles: RoleListLike,
    required: RoleListLike,
) -> bool:
    """True if the actor has all required roles."""
    actor = set(normalize_roles(actor_roles))
    req = set(normalize_roles(required))
    return req.issubset(actor)

def is_at_least(
    actor_roles: RoleListLike,
    minimum: RoleLike,
) -> bool:
    """
    True if ANY of the actor's roles is >= minimum in the hierarchy.
    Example:
      is_at_least(["TENANT_USER", "TENANT_ADMIN"], "TENANT_USER") -> True
      is_at_least("TENANT_ADMIN", "RESELLER_ADMIN") -> False
    """
    roles = normalize_roles(actor_roles)
    min_rank = _rank(_to_role(minimum))
    return any(_rank(r) >= min_rank for r in roles)

def is_strictly_above(
    actor_roles: RoleListLike,
    other: RoleLike,
) -> bool:
    """True if ANY actor role outranks the given role."""
    roles = normalize_roles(actor_roles)
    other_rank = _rank(_to_role(other))
    return any(_rank(r) > other_rank for r in roles)

def has_min_role(actor_roles: RoleListLike, minimum: RoleLike) -> bool:
    min_role = _to_role(minimum)
    return any(r.is_at_least(min_role) for r in _normalize(actor_roles))


def can_manage_user(
    actor_role: RoleLike,
    actor_tenant_id: Any,
    target_role: RoleLike,
    target_tenant_id: Any,
) -> bool:
    """Tenant-aware manage permission."""
    ar = _to_role(actor_role)
    tr = _to_role(target_role)

    # SUPER_ADMIN can manage anyone
    if ar == Role.SUPER_ADMIN:
        return ar.can_manage_role(tr)

    # RESELLER_ADMIN: same tenant for now (extend to reseller tree later)
    if ar == Role.RESELLER_ADMIN:
        return actor_tenant_id == target_tenant_id and ar.can_manage_role(tr)

    # TENANT_ADMIN: same tenant, and only manage TENANT_USER
    if ar == Role.TENANT_ADMIN:
        return actor_tenant_id == target_tenant_id and tr in (Role.TENANT_USER,)

    # Everyone else: cannot manage
    return False


# ---- Policy Objects (optional, for DI/Testing) -------------------------------

@dataclass(frozen=True)
class RbacPolicy:
    """
    Immutable policy service. Useful if you prefer DI over module-level funcs.
    """

    def normalize(self, roles: RoleListLike) -> list[Role]:
        return normalize_roles(roles)

    def has_any(self, actor_roles: RoleListLike, required: RoleListLike) -> bool:
        return has_any_role(actor_roles, required)

    def has_all(self, actor_roles: RoleListLike, required: RoleListLike) -> bool:
        return has_all_roles(actor_roles, required)

    def at_least(self, actor_roles: RoleListLike, minimum: RoleLike) -> bool:
        return is_at_least(actor_roles, minimum)

    def strictly_above(self, actor_roles: RoleListLike, other: RoleLike) -> bool:
        return is_strictly_above(actor_roles, other)
    
    @staticmethod
    def can_manage_user(
        actor_role: RoleLike,
        actor_tenant_id: Any,
        target_role: RoleLike,
        target_tenant_id: Any,
    ) -> bool:
        return can_manage_user(actor_role, actor_tenant_id, target_role, target_tenant_id)
    
    @staticmethod
    def has_min_role(actor_roles: RoleListLike, minimum: RoleLike) -> bool:
        return has_min_role(actor_roles, minimum)


# ---- Convenience Guards (pure functions, no FastAPI dependency here) ---------

@overload
def require_any_role(actor_roles: RoleListLike, required: RoleListLike) -> None: ...
@overload
def require_any_role(actor_roles: RoleListLike, required: RoleLike) -> None: ...

def require_any_role(actor_roles: RoleListLike, required: RoleListLike | RoleLike) -> None:
    """Raise PermissionError if actor lacks ANY of the required roles."""
    if not has_any_role(actor_roles, required):
        raise PermissionError("forbidden: missing required role(s)")

def require_all_roles(actor_roles: RoleListLike, required: RoleListLike | RoleLike) -> None:
    """Raise PermissionError if actor lacks ALL required roles."""
    if not has_all_roles(actor_roles, required):
        raise PermissionError("forbidden: requires all specified roles")

def require_min_role(actor_roles: RoleListLike, minimum: RoleLike) -> None:
    """Raise PermissionError if actor doesn't meet minimum role threshold."""
    if not is_at_least(actor_roles, minimum):
        raise PermissionError("forbidden: insufficient role level")


# ---- Notes -------------------------------------------------------------------
# - Keep this file framework-agnostic (no FastAPI imports).
# - API layer can wrap these with HTTP-friendly exceptions mapping to your
#   ERROR CONTRACT (e.g., translate PermissionError → 403 with code "forbidden").
# - This module is domain-level; it adheres to SRP and is easily unit-testable.
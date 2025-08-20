from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime, timedelta, timezone
from typing import Any, List, Optional, TypedDict
from uuid import UUID

from fastapi import Depends, Header, HTTPException, status, Security
from jose import jwt, JWTError
from jose.exceptions import ExpiredSignatureError
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import settings
from src.shared.database import get_session
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from src.identity.domain.entities import Principal
# -----------------------------------------------------------------------------
# Public types
# -----------------------------------------------------------------------------
ALLOWED_ROLES = {"PLATFORM_OWNER", "RESELLER","CLIENT"}

bearer = HTTPBearer(auto_error=False)


# -----------------------------------------------------------------------------
# JWT helpers
# -----------------------------------------------------------------------------
def create_access_token(
    *,
    subject: str,
    tenant_id: UUID,
    roles: List[str],
    expires_minutes: Optional[int] = None,
) -> str:
    """
    Build a signed JWT with the platform's required claims.
    """
    exp_min = expires_minutes if expires_minutes is not None else getattr(settings, "JWT_EXPIRE_MIN", 60)
    now = datetime.now(tz=timezone.utc)
    payload = {
        "sub": subject,
        "tenant_id": tenant_id,
        "roles": roles,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=exp_min)).timestamp()),
    }
    secret = getattr(settings.JWT_SECRET, "get_secret_value", lambda: settings.JWT_SECRET)()
    return jwt.encode(payload, secret, algorithm=settings.JWT_ALG)

def _secret_alg() -> tuple[str, str]:
    raw = settings.JWT_SECRET
    secret = raw.get_secret_value() if hasattr(raw, "get_secret_value") else (raw if isinstance(raw, str) else "")
    if not secret:
        raise HTTPException(status_code=500, detail="JWT secret not configured")
    alg = getattr(settings, "JWT_ALG", "HS256")
    return secret, alg

def decode_token(token: str) -> dict:
    """
    Verify and decode a JWT. Raises FastAPI HTTP 401 on failure.
    """
    try:
        secret = getattr(settings.JWT_SECRET, "get_secret_value", lambda: settings.JWT_SECRET)()
        return jwt.decode(token, secret, algorithms=[settings.JWT_ALG])
    except ExpiredSignatureError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token expired")
    except JWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")

def _pick(d: dict[str, Any], *keys: str, default=None):
    for k in keys:
        if k in d and d[k] is not None:
            return d[k]
    return default

def _as_roles(v: Any) -> set[str]:
    if v is None:
        return set()
    out: set[str] = set()
    if isinstance(v, str):
        out = {s.strip().upper() for s in v.replace(",", " ").split() if s.strip()}
    elif isinstance(v, dict):
        out = {k.upper() for k, ok in v.items() if ok}
    elif isinstance(v, Iterable):
        out = {str(x).upper() for x in v if isinstance(x, str)}
    if ALLOWED_ROLES:
        out = {r for r in out if r in ALLOWED_ROLES}
    return out

def _get_secret_and_alg() -> tuple[str, str]:
    raw = settings.JWT_SECRET
    secret = raw.get_secret_value() if hasattr(raw, "get_secret_value") else (raw if isinstance(raw, str) else "")
    if not secret:
        # Misconfiguration – .env not loaded or empty
        raise HTTPException(status_code=500, detail="JWT secret not configured")
    alg = getattr(settings, "JWT_ALG", "HS256")
    return secret, alg
# -----------------------------------------------------------------------------
# FastAPI dependencies
# -----------------------------------------------------------------------------
async def get_principal(credentials: HTTPAuthorizationCredentials | None = Security(bearer)) -> Principal | None:
    """
    Parse + verify JWT ONLY. No DB calls here (so /whoami can't 500).
    Returns None if no/invalid header on public routes.
    """
    if credentials is None or (credentials.scheme or "").lower() != "bearer":
        return None
    token = (credentials.credentials or "").strip()
    secret, alg = _secret_alg()
    try:
        claims = jwt.decode(token, secret, algorithms=[alg])
    except ExpiredSignatureError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token expired")
    except JWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")

    user_id = _pick(claims, "user_id", "uid", "sub")
    tenant  = _pick(claims, "tenant_id", "tenantId", "tid")
    email   = _pick(claims, "email", "preferred_username")
    if not email:
        # If sub looks like an email, use it as email too
        sub_val = _pick(claims, "sub")
        if sub_val and "@" in str(sub_val):
            email = str(sub_val)

    def _as_uuid(x):
        try:
            return UUID(str(x)) if x else None
        except Exception:
            return None

    return Principal(
        user_id=_as_uuid(user_id),
        tenant_id=_as_uuid(tenant),
        email=email,
        roles=_as_roles(_pick(claims, "roles", "role", "permissions", "scopes")),
    )

def require_roles(*required: str):
    req = {r.upper() for r in required}
    async def _dep(
        principal: Principal | None = Depends(get_principal),
        session: AsyncSession = Depends(get_session),
    ) -> Principal:
        if principal is None:
            raise HTTPException(status_code=401, detail="Authentication required")
        if not principal.roles or principal.roles.isdisjoint(req):
            raise HTTPException(status_code=403, detail="Insufficient role")
        # Try to set RLS tenant for this transaction; ignore if DB doesn’t support the GUC
        if principal.tenant_id:
            try:
                await session.execute(text("SELECT set_config('app.jwt_tenant', :tid, true)"), {"tid": str(principal.tenant_id)},
)

            except Exception:
                pass
        return principal
    return _dep

# -----------------------------------------------------------------------------
# Webhook signature verification (used by messaging webhooks)
# -----------------------------------------------------------------------------
def verify_hub_signature(raw_body: bytes, app_secret: str | bytes, provided_signature: Optional[str]) -> bool:
    """
    Validate X-Hub-Signature-256 header using HMAC-SHA256.
    Returns True if valid; False otherwise.
    """
    if not provided_signature or not provided_signature.startswith("sha256="):
        return False

    import hmac, hashlib

    if isinstance(app_secret, str):
        key = app_secret.encode("utf-8")
    else:
        key = app_secret

    expected = hmac.new(key, raw_body, hashlib.sha256).hexdigest()
    # Header may be either "sha256=HEX" or just HEX; handle both robustly
    provided_hex = provided_signature.split("=", 1)[1] if "=" in provided_signature else provided_signature
    try:
        return hmac.compare_digest(provided_hex, expected)
    except Exception:
        return False

async def get_tenant_from_header(x_tenant_id: Optional[str] = Header(None)) -> Optional[str]:
    """Bootstrap-only: allow tenant via header (id/code acceptable upstream)."""
    if not x_tenant_id:
        return None
    return x_tenant_id

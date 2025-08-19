from __future__ import annotations
from datetime import timedelta
import time
from typing import List, Optional
from fastapi import Depends, HTTPException, status, Header
from pydantic import BaseModel
from src.config import settings
from uuid import UUID
import hmac, hashlib
from jose import jwt, JWTError
from typing import TypedDict, Optional
from src.shared.database import get_session
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from jose.exceptions import ExpiredSignatureError

class TokenData(BaseModel):
    sub: str
    tenant_id: UUID
    roles: List[str]
    iat: int
    exp: int

# def create_access_token(*, user_id: str, tenant_id: str, roles: List[str]) -> str:
#     now = int(time.time())
#     exp = now + Settings.JWT_EXPIRE_MIN * 60
#     payload = {"sub": user_id, "tenant_id": tenant_id, "roles": roles, "iat": now, "exp": exp}
#     return jwt.encode(payload, Settings.JWT_SECRET, algorithm=Settings.JWT_ALG)

def create_access_token(sub: str, roles: list[str], tenant_id: UUID, expires_delta: timedelta | None = None):
    to_encode = {"sub": sub, "roles": roles, "tenant_id": tenant_id, "iat": int(time.time())}
    ttl = int(expires_delta.total_seconds()) if expires_delta else (settings.JWT_EXPIRE_MIN * 60)
    to_encode["exp"] = int(time.time() + ttl)
    return jwt.encode(to_encode, settings.JWT_SECRET, algorithm=settings.JWT_ALG)

def decode_token(token: str) -> dict:
    try:
        return jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALG])
    except ExpiredSignatureError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token expired")
    except JWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    
def require_roles(*required: str):
    async def _dep(principal: Optional[Principal] = Depends(get_principal)):
        if principal is None:
            raise HTTPException(status_code=401, detail="Authentication required")
        if not any(r in principal["roles"] for r in required):
            raise HTTPException(status_code=403, detail="Insufficient role")
        return principal
    return _dep

async def get_tenant_from_header(x_tenant_id: Optional[str] = Header(None)) -> Optional[str]:
    """Bootstrap-only: allow tenant via header (id/code acceptable upstream)."""
    if not x_tenant_id:
        return None
    return x_tenant_id

def verify_hub_signature(raw_body: bytes, app_secret: str, signature_header: Optional[str]) -> bool:
    """
    Verify X-Hub-Signature-256 = 'sha256=<hex>'.
    """
    if not signature_header or not signature_header.startswith("sha256="):
        return False
    supplied = signature_header.split("=", 1)[1].strip()
    mac = hmac.new(app_secret.encode("utf-8"), msg=raw_body, digestmod=hashlib.sha256)
    expected = mac.hexdigest()
    try:
        return hmac.compare_digest(supplied, expected)
    except Exception:
        return False
    
class Principal(TypedDict):
    sub: str
    tenant_id: UUID
    roles: list[str]

async def get_principal(
    authorization: Optional[str] = Header(None, alias="Authorization"),
    session: AsyncSession = Depends(get_session),
) -> Optional[Principal]:
    if not authorization or not authorization.startswith("Bearer "):
        return None
    # token = authorization.split(" ", 1)[1]
    # payload = jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALG])
    token = authorization.split(" ", 1)[1]
    # decode with proper 401s on error
    payload = decode_token(token)
    await session.execute(text("set local app.jwt_tenant = :tenant"), {"tenant": str(payload["tenant_id"])})
    return {"sub": payload["sub"], "tenant_id": payload["tenant_id"], "roles": payload.get("roles", [])}


# tests expect this alias
def issue_token(sub: str, tenant_id: UUID, roles: list[str]) -> str:
    return create_access_token(sub=sub, roles=roles, tenant_id=tenant_id)

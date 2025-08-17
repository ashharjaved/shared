from __future__ import annotations
import time, jwt
from typing import List, Optional
from fastapi import Depends, HTTPException, status, Header
from pydantic import BaseModel
from ..config import settings
from uuid import UUID
from src.identity.domain.entities import Principal

class TokenData(BaseModel):
    sub: str
    tenant_id: str
    roles: List[str]
    iat: int
    exp: int

def create_access_token(*, user_id: str, tenant_id: str, roles: List[str]) -> str:
    now = int(time.time())
    exp = now + settings.JWT_EXPIRE_MIN * 60
    payload = {"sub": user_id, "tenant_id": tenant_id, "roles": roles, "iat": now, "exp": exp}
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALG)

def decode_token(token: str) -> TokenData:
    try:
        data = jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALG])
        return TokenData(**data)
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")

async def get_principal(authorization: Optional[str] = Header(None)) -> Optional[Principal]:
    if not authorization:
        return None
    try:
        scheme, token = authorization.split(" ", 1)
    except ValueError:
        raise HTTPException(status_code=401, detail="Invalid Authorization header")
    if scheme.lower() != "bearer":
        raise HTTPException(status_code=401, detail="Bearer token required")
    td = decode_token(token)
    return Principal(user_id=td.sub, tenant_id=td.tenant_id, roles=td.roles)

def require_roles(*required: str):
    async def _dep(principal: Optional[Principal] = Depends(get_principal)):
        if principal is None:
            raise HTTPException(status_code=401, detail="Authentication required")
        if not any(r in principal.roles for r in required):
            raise HTTPException(status_code=403, detail="Insufficient role")
        return principal
    return _dep

async def get_tenant_from_header(x_tenant_id: Optional[str] = Header(None)) -> Optional[str]:
    """Bootstrap-only: allow tenant via header (id/code acceptable upstream)."""
    if not x_tenant_id:
        return None
    return x_tenant_id

# --- APPEND-ONLY: Identity dependencies ---
from fastapi import Depends, HTTPException, status, Request
from jose import jwt, JWTError
from uuid import UUID
from typing import Optional, Dict, Any
from .database import get_session, set_rls_guc, AsyncSession
import os

def _jwt_secret() -> str: return os.getenv("JWT_SECRET", "dev-insecure-secret-change-me")
def _jwt_alg() -> str: return os.getenv("JWT_ALG", "HS256")

async def get_db_session(session: AsyncSession = Depends(get_session)) -> AsyncSession:
    return session

def _extract_bearer(req: Request) -> str:
    auth = req.headers.get("Authorization", "")
    if not auth.lower().startswith("bearer "): raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail={"code":"unauthorized","message":"missing_token"})
    return auth.split(" ", 1)[1].strip()

async def get_current_user_claims(req: Request) -> Dict[str, Any]:
    token = _extract_bearer(req)
    try:
        payload = jwt.decode(token, _jwt_secret(), algorithms=[_jwt_alg()])
    except JWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail={"code":"unauthorized","message":"invalid_token"})
    # enrich with email when available (optional)
    return payload

async def get_tenant_id_from_jwt(claims=Depends(get_current_user_claims)) -> UUID:
    try:
        return UUID(claims["tenant_id"])
    except Exception:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail={"code":"unauthorized","message":"invalid_token_claims"})

async def enforce_rls(session=Depends(get_db_session), tenant_id: Optional[UUID]=None, claims=Depends(get_current_user_claims)):
    # Set GUCs per RLS contract
    await set_rls_guc(session, tenant_id=str(tenant_id) if tenant_id else None,
                      user_id=str(claims.get("sub")) if claims else None,
                      roles=str(claims.get("role")) if claims else None)
    return True
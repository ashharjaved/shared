# src/identity/api/routes/auth.py
from __future__ import annotations
from datetime import timedelta
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from src.identity.api.schemas import LoginRequest, LoginResponse, RefreshRequest
from src.shared import security
from src.shared.exceptions import AuthenticationError
from src.shared.error_codes import ERROR_CODES
from src.dependencies import get_user_repo
from src.identity.application.services.auth_service import AuthService

from src.config import get_settings

settings=get_settings()

router = APIRouter(prefix="/api/identity/auth", tags=["identity:auth"])


@router.post("/login", response_model=LoginResponse)
async def login(payload: LoginRequest, request: Request, user_repo=Depends(get_user_repo)) -> LoginResponse:
    service = AuthService(user_repository=user_repo)
    try:
        tokens = await service.authenticate_user(email=payload.email, password=payload.password,tenant_id=payload.tenant_id, correlation_id=request.headers.get("X-Correlation-ID",""))
    except AuthenticationError as e:
        raise HTTPException(status_code=e.status_code, detail={"code": e.code, "message": str(e)})
    return LoginResponse(access_token=tokens["access_token"], refresh_token=tokens.get("refresh_token"), expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES)


@router.post("/refresh", response_model=LoginResponse)
async def refresh(payload: RefreshRequest) -> LoginResponse:
    # Decode refresh token, validate type, and mint new access (and optionally a new refresh).
    try:
        claims = security.decode_token(payload.refresh_token)
        if claims.get("type") != "refresh":
            data = ERROR_CODES["invalid_credentials"]
            raise HTTPException(status_code=data["http"], detail={"code": "invalid_credentials", "message": "Invalid refresh token."})
        access = security.create_access_token(sub=claims["sub"], tenant_id=claims["tenant_id"], role=claims["role"], expires_delta=timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES))
        # Optionally rotate refresh:
        refresh_token = security.create_refresh_token(sub=claims["sub"], tenant_id=claims["tenant_id"], role=claims["role"], expires_delta=timedelta(minutes=settings.REFRESH_TOKEN_EXPIRE_MINUTES))
        return LoginResponse(access_token=access, refresh_token=refresh_token, expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    except Exception:
        data = ERROR_CODES["invalid_credentials"]
        raise HTTPException(status_code=data["http"], detail={"code": "invalid_credentials", "message": "Invalid refresh token."})


@router.post("/logout", status_code=status.HTTP_200_OK)
async def logout() -> None:
    # If you maintain a refresh-token allowlist/denylist in Redis, revoke here.
    # Stateless JWT access tokens cannot be revoked without additional infra.
    return None
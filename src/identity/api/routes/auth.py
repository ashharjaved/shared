"""
Authentication Routes
"""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Request, HTTPException, status

from shared.infrastructure.observability.logger import get_logger
from src.identity.api.schemas.auth_schemas import (
    LoginRequest,
    LoginResponse,
    RefreshTokenRequest,
    RefreshTokenResponse,
    PasswordResetRequest,
    PasswordResetResponse,
    PasswordResetConfirmRequest,
    EmailVerificationRequest,
    EmailVerificationResponse,
)
from src.identity.api.dependencies import (
    get_current_user,
    get_uow,
    get_jwt_service,
    CurrentUser,
)
from src.identity.application.services.auth_service import AuthService
from src.identity.infrastructure.adapters.identity_unit_of_work import IdentityUnitOfWork
from src.identity.infrastructure.adapters.jwt_service import JWTService

logger = get_logger(__name__)

router = APIRouter()


@router.post(
    "/login",
    response_model=LoginResponse,
    status_code=status.HTTP_200_OK,
    summary="User Login",
    description="Authenticate user and return JWT tokens",
)
async def login(
    request: Request,
    body: LoginRequest,
    uow: Annotated[IdentityUnitOfWork, Depends(get_uow)],
    jwt_service: Annotated[JWTService, Depends(get_jwt_service)],
) -> LoginResponse:
    """
    Authenticate user with email and password.
    
    Returns access token (15min) and refresh token (7 days).
    """
    auth_service = AuthService(uow, jwt_service)
    
    # Get client info
    ip_address = request.client.host if request.client else None
    user_agent = request.headers.get("User-Agent")
    
    result = await auth_service.login(
        email=body.email,
        password=body.password,
        ip_address=ip_address,
        user_agent=user_agent,
    )
    
    if result.is_failure():
        logger.warning(
            f"Login failed: {result.error}",
            extra={"email": body.email, "ip": ip_address},
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "code": "invalid_credentials",
                "message": result.error,
            },
        )
    
    login_dto = result.value
    
    return LoginResponse(
        access_token=login_dto.access_token,
        refresh_token=login_dto.refresh_token,
        token_type=login_dto.token_type,
        expires_in=login_dto.expires_in,
        user_id=login_dto.user_id,
        organization_id=login_dto.organization_id,
        email=login_dto.email,
        roles=login_dto.roles,
    )


@router.post(
    "/refresh",
    response_model=RefreshTokenResponse,
    status_code=status.HTTP_200_OK,
    summary="Refresh Access Token",
    description="Get new access token using refresh token",
)
async def refresh_token(
    body: RefreshTokenRequest,
    uow: Annotated[IdentityUnitOfWork, Depends(get_uow)],
    jwt_service: Annotated[JWTService, Depends(get_jwt_service)],
) -> RefreshTokenResponse:
    """
    Refresh access token using refresh token.
    
    Implements token rotation - old refresh token is revoked.
    """
    auth_service = AuthService(uow, jwt_service)
    
    result = await auth_service.refresh_token(body.refresh_token)
    
    if result.is_failure():
        logger.warning(f"Token refresh failed: {result.error}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "code": "invalid_token",
                "message": result.error,
            },
        )
    
    login_dto = result.value
    
    return RefreshTokenResponse(
        access_token=login_dto.access_token,
        refresh_token=login_dto.refresh_token,
        token_type=login_dto.token_type,
        expires_in=login_dto.expires_in,
        user_id=login_dto.user_id,
        organization_id=login_dto.organization_id,
        email=login_dto.email,
        roles=login_dto.roles,
    )


@router.get(
    "/me",
    response_model=dict,
    status_code=status.HTTP_200_OK,
    summary="Get Current User",
    description="Get current authenticated user info from token",
)
async def get_me(
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
) -> dict:
    """
    Get current user information from JWT token.
    
    Requires authentication.
    """
    return {
        "user_id": str(current_user.user_id),
        "organization_id": str(current_user.organization_id),
        "email": current_user.email,
        "roles": current_user.roles,
        "permissions": current_user.permissions,
    }


@router.post(
    "/password-reset/request",
    response_model=PasswordResetResponse,
    status_code=status.HTTP_200_OK,
    summary="Request Password Reset",
    description="Send password reset email (always returns success to prevent email enumeration)",
)
async def request_password_reset(
    request: Request,
    body: PasswordResetRequest,
    uow: Annotated[IdentityUnitOfWork, Depends(get_uow)],
    jwt_service: Annotated[JWTService, Depends(get_jwt_service)],
) -> PasswordResetResponse:
    """
    Request password reset.
    
    Always returns success to prevent email enumeration attacks.
    If email exists, sends reset link.
    """
    auth_service = AuthService(uow, jwt_service)
    
    ip_address = request.client.host if request.client else None
    
    # Always returns success
    await auth_service.request_password_reset(
        email=body.email,
        ip_address=ip_address,
    )
    
    return PasswordResetResponse(
        message="If the email exists, a password reset link has been sent"
    )


@router.post(
    "/password-reset/confirm",
    response_model=PasswordResetResponse,
    status_code=status.HTTP_200_OK,
    summary="Confirm Password Reset",
    description="Reset password using reset token",
)
async def confirm_password_reset(
    request: Request,
    body: PasswordResetConfirmRequest,
    uow: Annotated[IdentityUnitOfWork, Depends(get_uow)],
    jwt_service: Annotated[JWTService, Depends(get_jwt_service)],
) -> PasswordResetResponse:
    """
    Reset password using reset token.
    
    Revokes all active sessions after password change.
    """
    auth_service = AuthService(uow, jwt_service)
    
    ip_address = request.client.host if request.client else None
    
    result = await auth_service.reset_password(
        reset_token=body.reset_token,
        new_password=body.new_password,
        ip_address=ip_address,
    )
    
    if result.is_failure():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "invalid_token",
                "message": result.error,
            },
        )
    
    return PasswordResetResponse(
        message="Password reset successfully. Please log in with your new password."
    )


@router.post(
    "/email/verify",
    response_model=EmailVerificationResponse,
    status_code=status.HTTP_200_OK,
    summary="Verify Email",
    description="Verify email using verification token",
)
async def verify_email(
    request: Request,
    body: EmailVerificationRequest,
    uow: Annotated[IdentityUnitOfWork, Depends(get_uow)],
    jwt_service: Annotated[JWTService, Depends(get_jwt_service)],
) -> EmailVerificationResponse:
    """
    Verify email address using verification token.
    """
    auth_service = AuthService(uow, jwt_service)
    
    ip_address = request.client.host if request.client else None
    
    result = await auth_service.verify_email(
        verification_token=body.verification_token,
        ip_address=ip_address,
    )
    
    if result.is_failure():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "invalid_token",
                "message": result.error,
            },
        )
    
    return EmailVerificationResponse(
        message="Email verified successfully",
        email_verified=True,
    )


@router.post(
    "/email/resend-verification",
    response_model=PasswordResetResponse,
    status_code=status.HTTP_200_OK,
    summary="Resend Email Verification",
    description="Resend email verification link",
)
async def resend_email_verification(
    request: Request,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    uow: Annotated[IdentityUnitOfWork, Depends(get_uow)],
    jwt_service: Annotated[JWTService, Depends(get_jwt_service)],
) -> PasswordResetResponse:
    """
    Resend email verification link to current user.
    
    Requires authentication.
    """
    auth_service = AuthService(uow, jwt_service)
    
    ip_address = request.client.host if request.client else None
    
    result = await auth_service.request_email_verification(
        user_id=current_user.user_id,
        organization_id=current_user.organization_id,
        ip_address=ip_address,
    )
    
    if result.is_failure():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "verification_failed",
                "message": result.error,
            },
        )
    
    return PasswordResetResponse(
        message="Verification email sent successfully"
    )
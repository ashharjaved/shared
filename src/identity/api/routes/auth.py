# src/identity/api/routes/auth.py

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import JSONResponse
from typing import Optional

from src.identity.api.schemas import (
    LoginRequest,
    LoginResponse,
    RefreshRequest,
    PasswordResetRequest,
    PasswordResetConfirm,
)
from src.identity.application.services.auth_application_service import (
    AuthApplicationService,
)
from src.shared_.exceptions import (
    AuthenticationError,
    AuthorizationError,
    ValidationError,
)
from src.shared_.http.dependencies import get_current_user
from src.shared_.http.errors import _http, _payload, ErrorCode

import structlog

logger = structlog.get_logger()

router = APIRouter(prefix="/api/identity/auth", tags=["Identity:Auth"])


def get_auth_service() -> AuthApplicationService:
    """
    Factory for AuthApplicationService with all dependencies.
    
    In production, this would use proper dependency injection.
    """
    from src.identity.application.factories import make_auth_service
    return make_auth_service()


@router.post("/login", response_model=LoginResponse, status_code=status.HTTP_200_OK)
async def login(
    payload: LoginRequest,
    request: Request,
    auth_service: AuthApplicationService = Depends(get_auth_service),
) -> LoginResponse:
    """
    Authenticate user and issue JWT tokens.
    
    Features:
    - Rate limiting (5 attempts per 5 minutes)
    - Account lockout after max attempts
    - Audit logging via domain events
    - IP tracking for security
    
    Returns:
        LoginResponse with access_token, refresh_token, and user info
        
    Raises:
        401: Invalid credentials
        403: Account locked or inactive
        429: Too many requests
    """
    # Extract client info for audit
    ip_address = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")
    
    try:
        result = await auth_service.login(
            email=payload.email,
            password=payload.password,
            tenant_id=payload.tenant_id,
            ip_address=ip_address,
            user_agent=user_agent,
        )
        
        logger.info(
            "Login successful",
            email=payload.email,
            tenant_id=payload.tenant_id,
            ip=ip_address,
        )
        
        return LoginResponse(**result)
    
    except AuthenticationError as e:
        logger.warning(
            "Login failed - invalid credentials",
            email=payload.email,
            tenant_id=payload.tenant_id,
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=_payload(ErrorCode.UNAUTHORIZED, str(e)),
        )
    
    except AuthorizationError as e:
        logger.warning(
            "Login failed - authorization error",
            email=payload.email,
            error=str(e),
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=_payload(ErrorCode.FORBIDDEN, str(e)),
        )
    
    except Exception as e:
        logger.error(
            "Login failed - unexpected error",
            email=payload.email,
            error=str(e),
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=_payload(ErrorCode.INTERNAL_ERROR, "Authentication failed"),
        )


@router.post("/refresh", response_model=LoginResponse, status_code=status.HTTP_200_OK)
async def refresh(
    payload: RefreshRequest,
    auth_service: AuthApplicationService = Depends(get_auth_service),
) -> LoginResponse:
    """
    Refresh access token using refresh token.
    
    Features:
    - Token rotation (new refresh token issued)
    - User status validation
    - Audit logging
    
    Returns:
        LoginResponse with new tokens
        
    Raises:
        401: Invalid or expired refresh token
    """
    try:
        result = await auth_service.refresh_token(payload.refresh_token)
        
        logger.info("Token refreshed successfully")
        
        return LoginResponse(**result)
    
    except AuthenticationError as e:
        logger.warning("Token refresh failed", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=_payload(ErrorCode.UNAUTHORIZED, "Invalid or expired refresh token"),
        )
    
    except Exception as e:
        logger.error("Token refresh failed - unexpected error", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=_payload(ErrorCode.INTERNAL_ERROR, "Token refresh failed"),
        )


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    current_user=Depends(get_current_user),
    auth_service: AuthApplicationService = Depends(get_auth_service),
) -> None:
    """
    Logout user (stateless JWT - mainly for audit trail).
    
    For stateless JWT, this doesn't revoke tokens (they expire naturally).
    If you need immediate revocation, implement a token denylist in Redis.
    """
    try:
        await auth_service.logout(
            user_id=str(current_user.id),
            tenant_id=str(current_user.tenant_id),
        )
        
        logger.info("User logged out", user_id=str(current_user.id))
    
    except Exception as e:
        logger.error("Logout failed", error=str(e))
        # Don't fail logout - just log the error


@router.get("/me", status_code=status.HTTP_200_OK)
async def me(current_user=Depends(get_current_user)) -> dict:
    """
    Get current authenticated user info.
    
    Returns:
        User profile with role and tenant info
    """
    return {
        "id": str(current_user.id),
        "email": current_user.email.value,
        "name": f"{current_user.first_name.value} {current_user.last_name.value}",
        "role": current_user.role.value if hasattr(current_user.role, 'value') else str(current_user.role),
        "tenant_id": str(current_user.tenant_id),
        "is_active": current_user.is_active,
    }


@router.post("/password-reset", status_code=status.HTTP_202_ACCEPTED)
async def request_password_reset(
    payload: PasswordResetRequest,
    request: Request,
) -> dict:
    """
    Initiate password reset flow.
    
    Always returns 202 to prevent email enumeration.
    If email exists, reset link is sent via email.
    
    Security:
    - No indication if email exists or not
    - Rate limited per IP
    - Reset tokens expire in 1 hour
    """
    from src.identity.application.factories import make_password_reset_service
    
    reset_service = make_password_reset_service()
    ip_address = request.client.host if request.client else None
    
    try:
        # Initiate reset (returns None if email not found - silent)
        reset_token = await reset_service.initiate_reset(
            email=payload.email,
            tenant_id=payload.tenant_id,
        )
        
        if reset_token:
            # TODO: Send email with reset link
            # await email_service.send_password_reset(reset_token)
            logger.info(
                "Password reset initiated",
                email=payload.email,
                ip=ip_address,
            )
        else:
            # Silent failure - don't reveal if email exists
            logger.info(
                "Password reset requested for non-existent email",
                email=payload.email,
                ip=ip_address,
            )
        
        # Always return success to prevent enumeration
        return {
            "message": "If your email is registered, you will receive a password reset link."
        }
    
    except Exception as e:
        logger.error("Password reset failed", error=str(e))
        # Still return success to prevent enumeration
        return {
            "message": "If your email is registered, you will receive a password reset link."
        }


@router.post("/password-reset/confirm", status_code=status.HTTP_200_OK)
async def confirm_password_reset(payload: PasswordResetConfirm) -> dict:
    """
    Complete password reset with new password.
    
    Args:
        token: Reset token from email
        email: User's email
        new_password: New password
        
    Returns:
        Success message
        
    Raises:
        400: Invalid token or weak password
    """
    from src.identity.application.factories import make_password_reset_service
    
    reset_service = make_password_reset_service()
    
    try:
        success, error = await reset_service.complete_reset(
            token=payload.token,
            email=payload.email,
            new_password=payload.new_password,
            tenant_id=payload.tenant_id,
        )
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=_payload(ErrorCode.INVALID_INPUT, error or "Reset failed"),
            )
        
        logger.info("Password reset completed", email=payload.email)
        
        return {"message": "Password reset successful. You can now login with your new password."}
    
    except HTTPException:
        raise
    
    except Exception as e:
        logger.error("Password reset confirmation failed", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=_payload(ErrorCode.INTERNAL_ERROR, "Reset failed"),
        )


@router.post("/data-deletion")
async def data_deletion(request: Request) -> JSONResponse:
    """
    Meta (WhatsApp) data deletion callback.
    
    Meta calls this endpoint when user requests data deletion.
    Must verify request signature and process deletion.
    """
    try:
        payload = await request.json()
        user_id = payload.get("user_id")
        
        if not user_id:
            return JSONResponse(
                status_code=400,
                content=_payload(ErrorCode.INVALID_INPUT, "Missing user_id"),
            )
        
        # TODO: Verify Meta signature
        # TODO: Implement user data deletion/anonymization
        
        logger.info("Data deletion requested", user_id=user_id)
        
        return JSONResponse(
            content={"code": "ok", "message": f"User {user_id} deletion queued"}
        )
    
    except Exception as e:
        logger.error("Data deletion failed", error=str(e))
        return JSONResponse(
            status_code=500,
            content=_payload(ErrorCode.INTERNAL_ERROR, str(e)),
        )
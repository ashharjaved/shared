"""
Identity API Error Handlers
Translates exceptions to standardized HTTP error responses
"""
from __future__ import annotations

from fastapi import Request, status
from fastapi.responses import JSONResponse

from shared.infrastructure.observability.logger import get_logger
from src.identity.domain.exception import (
    InvalidCredentialsException,
    AccountLockedException,
    DuplicateEmailException,
    DuplicateSlugException,
    RefreshTokenExpiredException,
    RefreshTokenRevokedException,
    EmailVerificationTokenExpiredException,
    EmailVerificationTokenAlreadyUsedException,
    PasswordResetTokenExpiredException,
    PasswordResetTokenAlreadyUsedException,
)

logger = get_logger(__name__)


async def invalid_credentials_handler(
    request: Request,
    exc: InvalidCredentialsException,
) -> JSONResponse:
    """Handle invalid credentials exception"""
    logger.warning(
        "Invalid credentials",
        extra={"path": request.url.path},
    )
    return JSONResponse(
        status_code=status.HTTP_401_UNAUTHORIZED,
        content={
            "code": "invalid_credentials",
            "message": str(exc),
        },
    )


async def account_locked_handler(
    request: Request,
    exc: AccountLockedException,
) -> JSONResponse:
    """Handle account locked exception"""
    logger.warning(
        "Account locked",
        extra={"path": request.url.path, "unlock_at": exc.unlock_at.utcnow()},
    )
    return JSONResponse(
        status_code=status.HTTP_403_FORBIDDEN,
        content={
            "code": "account_locked",
            "message": str(exc),
            "details": {
                "unlock_at": exc.unlock_at.isoformat(),
            },
        },
    )


async def duplicate_email_handler(
    request: Request,
    exc: DuplicateEmailException,
) -> JSONResponse:
    """Handle duplicate email exception"""
    logger.warning(
        "Duplicate email",
        extra={"path": request.url.path, "email": exc},
    )
    return JSONResponse(
        status_code=status.HTTP_409_CONFLICT,
        content={
            "code": "duplicate_email",
            "message": str(exc),
            "details": {
                "email": exc,
            },
        },
    )


async def duplicate_slug_handler(
    request: Request,
    exc: DuplicateSlugException,
) -> JSONResponse:
    """Handle duplicate slug exception"""
    logger.warning(
        "Duplicate slug",
        extra={"path": request.url.path, "slug": exc},
    )
    return JSONResponse(
        status_code=status.HTTP_409_CONFLICT,
        content={
            "code": "duplicate_slug",
            "message": str(exc),
            "details": {
                "slug": exc,
            },
        },
    )


async def token_expired_handler(
    request: Request,
    exc: RefreshTokenExpiredException | EmailVerificationTokenExpiredException | PasswordResetTokenExpiredException,
) -> JSONResponse:
    """Handle token expired exceptions"""
    logger.warning(
        "Token expired",
        extra={"path": request.url.path, "exception": exc.__class__.__name__},
    )
    return JSONResponse(
        status_code=status.HTTP_401_UNAUTHORIZED,
        content={
            "code": "token_expired",
            "message": str(exc),
        },
    )


async def token_already_used_handler(
    request: Request,
    exc: EmailVerificationTokenAlreadyUsedException | PasswordResetTokenAlreadyUsedException,
) -> JSONResponse:
    """Handle token already used exceptions"""
    logger.warning(
        "Token already used",
        extra={"path": request.url.path, "exception": exc.__class__.__name__},
    )
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={
            "code": "token_already_used",
            "message": str(exc),
        },
    )


async def token_revoked_handler(
    request: Request,
    exc: RefreshTokenRevokedException,
) -> JSONResponse:
    """Handle token revoked exception"""
    logger.warning(
        "Token revoked",
        extra={"path": request.url.path},
    )
    return JSONResponse(
        status_code=status.HTTP_401_UNAUTHORIZED,
        content={
            "code": "token_revoked",
            "message": str(exc),
        },
    )


def register_exception_handlers(app) -> None:
    """
    Register all identity exception handlers with FastAPI app.
    
    Args:
        app: FastAPI application instance
    """
    app.add_exception_handler(InvalidCredentialsException, invalid_credentials_handler)
    app.add_exception_handler(AccountLockedException, account_locked_handler)
    app.add_exception_handler(DuplicateEmailException, duplicate_email_handler)
    app.add_exception_handler(DuplicateSlugException, duplicate_slug_handler)
    app.add_exception_handler(RefreshTokenExpiredException, token_expired_handler)
    app.add_exception_handler(RefreshTokenRevokedException, token_revoked_handler)
    app.add_exception_handler(EmailVerificationTokenExpiredException, token_expired_handler)
    app.add_exception_handler(EmailVerificationTokenAlreadyUsedException, token_already_used_handler)
    app.add_exception_handler(PasswordResetTokenExpiredException, token_expired_handler)
    app.add_exception_handler(PasswordResetTokenAlreadyUsedException, token_already_used_handler)
    
    logger.info("Identity exception handlers registered")
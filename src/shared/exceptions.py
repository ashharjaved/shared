from typing import Any, Dict, Optional
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from pydantic import ValidationError as PydanticValidationError
from fastapi.exceptions import RequestValidationError
from fastapi import HTTPException, status

from src.shared.error_codes import ERROR_CODES

# ───────────────────────── Base & Domain Exceptions ─────────────────────────
class DomainError(Exception):
    """Base class for domain-level errors. Services should raise these, never HTTPException."""
    code: str = "domain_error"
    status_code: int = status.HTTP_400_BAD_REQUEST
    message: str
    details: Optional[Dict[str, Any]]

    def __init__(
        self,
        message: str = "",
        *,
        code: Optional[str] = None,
        status_code: Optional[int] = None,
        details: Optional[Dict[str, Any]] = None,
        extra: Optional[Dict[str, Any]] = None,
    ) -> None:
        super().__init__(message or self.__class__.__name__)
        if code is not None:
            self.code = code
        if status_code is not None:
            self.status_code = status_code
        # prefer explicit details; fall back to extra (back-compat with older callers)
        self.message = message or self.__class__.__name__
        self.details = details if details is not None else (extra or None)


class DomainConflictError(DomainError):
    code = "conflict"
    status_code = status.HTTP_409_CONFLICT

class AuthenticationError(DomainError):
    code, status_code = "unauthorized", status.HTTP_401_UNAUTHORIZED

class ValidationError(DomainError):
    code = "validation_error"
    status_code = status.HTTP_422_UNPROCESSABLE_ENTITY


class UnauthorizedError(DomainError):
    code = "unauthorized"
    status_code = status.HTTP_401_UNAUTHORIZED

class AuthorizationError(DomainError):
    code, status_code = "forbidden", status.HTTP_403_FORBIDDEN

class InvalidCredentialsError(DomainError):
    code = "invalid_credentials"
    status_code = status.HTTP_401_UNAUTHORIZED

class ForbiddenError(DomainError):
    code = "forbidden"
    status_code = status.HTTP_403_FORBIDDEN


class NotFoundError(DomainError):
    # generic; set a specific code via constructor if needed (e.g., "user_not_found")
    code = "not_found"
    status_code = status.HTTP_404_NOT_FOUND


class ConflictError(DomainError):
    code = "conflict"
    status_code = status.HTTP_409_CONFLICT


class IdempotencyConflictError(DomainError):
    code = "idempotency_conflict"
    status_code = status.HTTP_409_CONFLICT


class RateLimitedError(DomainError):
    code = "rate_limited"
    status_code = status.HTTP_429_TOO_MANY_REQUESTS


class InternalServerError(DomainError):
    code = "internal_error"
    status_code = status.HTTP_500_INTERNAL_SERVER_ERROR


class RlsNotSetError(DomainError):
    code = "rls_not_set"
    status_code = status.HTTP_500_INTERNAL_SERVER_ERROR

class AccountLockedError(DomainError):
    code = "account_locked"
    # Align with contract: account_locked is treated as 403 Forbidden
    status_code = status.HTTP_403_FORBIDDEN

class CryptoError(DomainError):
    code = "crypto_error"
    status_code = status.HTTP_500_INTERNAL_SERVER_ERROR

# ───────────────────────────── Helpers ──────────────────────────────────────

def _problem(
    code: str,
    message: str,
    details: Optional[Dict[str, Any]],
    correlation_id: Optional[str],
) -> Dict[str, Any]:
    body: Dict[str, Any] = {"code": code, "message": message}
    if details:
        body["details"] = details
    if correlation_id:
        body["correlation_id"] = correlation_id
    return body


def _extract_correlation_id(req: Request) -> Optional[str]:
    return getattr(getattr(req, "state", None), "request_id", None)

def _http_for(code: str) -> int:
    return int(ERROR_CODES.get(code, {}).get("http", status.HTTP_500_INTERNAL_SERVER_ERROR))

def _msg_for(code: str) -> str:
    return str(ERROR_CODES.get(code, {}).get("message", code))

# ─────────────────────────── Registration ───────────────────────────

def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(DomainError)
    async def handle_app_error(req: Request, exc: DomainError):
        return JSONResponse(
            status_code=exc.status_code,
            content=_problem(exc.code, exc.message, exc.details, _extract_correlation_id(req)),
        )

    @app.exception_handler(RequestValidationError)
    async def handle_request_validation(req: Request, exc: RequestValidationError):
        code = "validation_error"
        return JSONResponse(
            status_code=_http_for(code),
            content=_problem(code, _msg_for(code), {"errors": exc.errors()}, _extract_correlation_id(req)),
        )

    @app.exception_handler(PydanticValidationError)
    async def handle_pydantic_validation(req: Request, exc: PydanticValidationError):
        code = "validation_error"
        return JSONResponse(
            status_code=_http_for(code),
            content=_problem(code, _msg_for(code), {"errors": exc.errors()}, _extract_correlation_id(req)),
        )

    @app.exception_handler(HTTPException)
    async def handle_http_exception(req: Request, exc: HTTPException):
        # map HTTP status → first matching ERROR_CODES entry
        reverse_map = {v["http"]: k for k, v in ERROR_CODES.items()}
        code = reverse_map.get(exc.status_code, "internal_error")
        detail = getattr(exc, "detail", None)
        details = detail if isinstance(detail, dict) else ({"detail": detail} if detail else None)
        return JSONResponse(
            status_code=exc.status_code,
            content=_problem(code, str(detail) if isinstance(detail, str) else _msg_for(code), details, _extract_correlation_id(req)),
        )

    @app.exception_handler(Exception)
    async def handle_unhandled(req: Request, exc: Exception):
        code = "internal_error"
        return JSONResponse(
            status_code=_http_for(code),
            content=_problem(code, _msg_for(code), {"type": exc.__class__.__name__}, _extract_correlation_id(req)),
        )
from __future__ import annotations

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.status import (
    HTTP_400_BAD_REQUEST,
    HTTP_401_UNAUTHORIZED,
    HTTP_403_FORBIDDEN,
    HTTP_404_NOT_FOUND,
    HTTP_409_CONFLICT,
    HTTP_422_UNPROCESSABLE_ENTITY,
    HTTP_429_TOO_MANY_REQUESTS,
    HTTP_500_INTERNAL_SERVER_ERROR,
)


class AppError(Exception):
    status_code: int = HTTP_400_BAD_REQUEST
    code: str = "invalid_request"

    def __init__(self, message: str = "Invalid request", details: dict | None = None):
        super().__init__(message)
        self.message = message
        self.details = details or {}

    def to_response(self) -> JSONResponse:
        return JSONResponse(
            status_code=self.status_code,
            content={"code": self.code, "message": self.message, "details": self.details},
        )


class ValidationError(AppError):
    status_code = HTTP_400_BAD_REQUEST
    code = "validation_error"


class UnauthorizedError(AppError):
    status_code = HTTP_401_UNAUTHORIZED
    code = "unauthorized"


class InvalidCredentialsError(AppError):
    status_code = HTTP_401_UNAUTHORIZED
    code = "invalid_credentials"


class ForbiddenError(AppError):
    status_code = HTTP_403_FORBIDDEN
    code = "forbidden"


class NotFoundError(AppError):
    status_code = HTTP_404_NOT_FOUND
    code = "not_found"


class ConflictError(AppError):
    status_code = HTTP_409_CONFLICT
    code = "conflict"


class RateLimitedError(AppError):
    status_code = HTTP_429_TOO_MANY_REQUESTS
    code = "rate_limited"


class InternalServerError(AppError):
    status_code = HTTP_500_INTERNAL_SERVER_ERROR
    code = "internal_error"


async def app_error_handler(_: Request, exc: AppError):
    return exc.to_response()


async def unhandled_error_handler(_: Request, exc: Exception):
    # We do not leak internals; message is generic per SECURITY_POLICY
    return JSONResponse(
        status_code=HTTP_500_INTERNAL_SERVER_ERROR,
        content={"code": "internal_error", "message": "Internal server error", "details": {}},
    )

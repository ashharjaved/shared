from __future__ import annotations
from typing import Any, Dict, Optional
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
import logging

logger = logging.getLogger(__name__)

class AppException(Exception):
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        self.message = message
        self.details = details or {}
        super().__init__(self.message)

class NotFoundError(AppException): ...
class ConflictError(AppException): ...
class AuthenticationError(AppException): ...
class AuthorizationError(AppException): ...
class ValidationError(AppException): ...

def add_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(NotFoundError)
    async def not_found_handler(_: Request, exc: NotFoundError):
        logger.warning("Not found: %s", exc.message, extra={"details": exc.details})
        return JSONResponse(status_code=404, content={"error": "not_found","message": exc.message,"details": exc.details})

    @app.exception_handler(ConflictError)
    async def conflict_handler(_: Request, exc: ConflictError):
        logger.warning("Conflict: %s", exc.message, extra={"details": exc.details})
        return JSONResponse(status_code=409, content={"error": "conflict","message": exc.message,"details": exc.details})

    @app.exception_handler(AuthenticationError)
    async def auth_handler(_: Request, exc: AuthenticationError):
        logger.warning("Authentication error: %s", exc.message)
        return JSONResponse(status_code=401, content={"error": "authentication_error","message": exc.message})

    @app.exception_handler(AuthorizationError)
    async def authz_handler(_: Request, exc: AuthorizationError):
        logger.warning("Authorization error: %s", exc.message)
        return JSONResponse(status_code=403, content={"error": "authorization_error","message": exc.message})

    @app.exception_handler(ValidationError)
    async def validation_handler(_: Request, exc: ValidationError):
        logger.warning("Validation error: %s", exc.message, extra={"details": exc.details})
        return JSONResponse(status_code=400, content={"error": "validation_error","message": exc.message,"details": exc.details})

    @app.exception_handler(RequestValidationError)
    async def request_validation_handler(_: Request, exc: RequestValidationError):
        logger.warning("Request validation error: %s", str(exc))
        return JSONResponse(status_code=422, content={"error": "request_validation_error","message": "Invalid request data","details": exc.errors()})

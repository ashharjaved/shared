from __future__ import annotations

from typing import Any, Dict

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import ValidationError
from starlette.middleware.base import BaseHTTPMiddleware

from src.shared.exceptions import DomainError
from src.shared.error_codes import ERROR_CODES
from src.shared.exceptions import register_exception_handlers  # central mapping
from src.dependencies import extract_bearer_token
from src.shared import security

# Identity routers (existing)
from src.identity.api.routes.auth import router as auth_router  # type: ignore
from src.identity.api.routes.users import router as users_router  # type: ignore
from src.identity.api.routes.tokens import router as tokens_router  # type: ignore

# Platform routers (new)
from src.platform.api.routes.config_routes import router as config_router
from src.platform.api.routes.limit_routes import router as limit_router


class JwtContextMiddleware(BaseHTTPMiddleware):
    """
    Parses Bearer JWT and attaches claims to request.state.user_claims.
    RLS GUCs are set later (DB dependency) using these claims.
    """

    async def dispatch(self, request: Request, call_next):
        token = extract_bearer_token(request)
        if token:
            try:
                claims = security.decode_token(token)
                request.state.user_claims = {
                    "sub": claims.get("sub"),
                    "tenant_id": claims.get("tenant_id"),
                    "role": claims.get("role"),
                }
            except Exception:
                request.state.user_claims = None
        else:
            request.state.user_claims = None

        return await call_next(request)


def _json(status: int, payload: Dict[str, Any]):
    from fastapi.responses import JSONResponse
    return JSONResponse(status_code=status, content=payload)


def create_app() -> FastAPI:
    app = FastAPI(
        title="Centralized WhatsApp Chatbot Platform — API",
        version="1.0.0",
    )

    # CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
        allow_credentials=True,
    )

    # JWT → request.state.user_claims
    app.add_middleware(JwtContextMiddleware)

    # Routers
    app.include_router(auth_router)
    app.include_router(users_router)
    app.include_router(tokens_router)
    app.include_router(config_router)
    app.include_router(limit_router)

    # Centralized error handling → {code, message, details?, correlation_id?}
    register_exception_handlers(app)

    # Back-compat handlers (kept harmless; central handler covers most)
    @app.exception_handler(DomainError)
    async def domain_error_handler(_req: Request, exc: DomainError):
        code = getattr(exc, "code", "domain_error")
        status = getattr(exc, "status_code", 400)
        return _json(
            status,
            {
                "code": code,
                "message": str(exc),
                "details": getattr(exc, "details", {}),
                "correlation_id": getattr(exc, "correlation_id", None),
            },
        )

    @app.exception_handler(ValidationError)
    async def validation_error_handler(_req: Request, exc: ValidationError):
        return _json(
            422,
            {
                "code": "validation_error",
                "message": "Validation failed.",
                "details": exc.errors(),
            },
        )

    return app


app = create_app()

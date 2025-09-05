from __future__ import annotations

from typing import Any, Dict

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi
from pydantic import ValidationError
from starlette.middleware.base import BaseHTTPMiddleware
from fastapi.encoders import jsonable_encoder
from src.shared.exceptions import DomainError
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

from src.messaging.api.routes.channels import router as channels_router
from src.messaging.api.routes.messages import router as messages_router
from src.messaging.api.routes.webhook import router as webhook_router
# Health router (new)
from src.shared.health import router as health_router
from src.conversation.api import router as conversation_router

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


def _json(status: int, payload: Dict[str, Any], headers: dict | None = None):
    from fastapi.responses import JSONResponse
    return JSONResponse(
        status_code=status,
        content=jsonable_encoder(payload),  # handles UUID, datetime, Decimal, sets, etc.
        headers=headers,
    )

def create_app() -> FastAPI:
    app = FastAPI(
        title="Centralized WhatsApp Chatbot Platform — API",
        version="1.0.0",
        swagger_ui_parameters={"persistAuthorization": True},
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
    app.include_router(health_router)
    app.include_router(channels_router)
    app.include_router(messages_router)
    app.include_router(webhook_router)
    app.include_router(conversation_router)

    # Centralized error handling → {code, message, details?, correlation_id?}
    register_exception_handlers(app)

    # Root endpoint
    @app.get("/", tags=["Root"])
    async def root():
        """Root endpoint."""
        return {
            "message": "WhatsApp Chatbot Platform API",
            "docs": "/docs",
            "health": "/health",
        }

    # Back-compat handlers
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

    # ---- Custom OpenAPI to add Bearer auth ----
    def custom_openapi():
        if app.openapi_schema:
            return app.openapi_schema
        schema = get_openapi(
            title=app.title,
            version=app.version,
            routes=app.routes,
        )
        schema.setdefault("components", {}).setdefault("securitySchemes", {})["bearerAuth"] = {
            "type": "http",
            "scheme": "bearer",
            "bearerFormat": "JWT",
        }
        schema["security"] = [{"bearerAuth": []}]
        app.openapi_schema = schema
        return schema

    app.openapi = custom_openapi

    return app


app = create_app()

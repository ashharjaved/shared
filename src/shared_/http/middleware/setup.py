from __future__ import annotations
import os

from fastapi import FastAPI

from .security_middleware import SecurityHeadersMiddleware, IpAllowlistMiddleware
from .request_id_middleware import RequestIdMiddleware
from .exception_middleware import ExceptionMiddleware
from .jwt_auth_middleware import JwtAuthMiddleware
from .context_middleware import ContextMiddleware
from .rls_middleware import RlsMiddleware
from .rate_limit_middleware import RateLimitMiddleware
from .logging_middleware import LoggingMiddleware

def setup_http_middlewares(app: FastAPI) -> None:
    """
    Configure middleware in correct order (outermost to innermost).
    """
    
    # 1. Security (outermost) - should be first
    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(
        IpAllowlistMiddleware, 
        allowlist_cidrs=[], 
        enabled=os.getenv("IP_ALLOWLIST_ENABLED", "false").lower() == "true"
    )
    
    # 2. Request ID (early for correlation)
    app.add_middleware(RequestIdMiddleware)
    
    # 3. Exception handling (catch everything below)
    app.add_middleware(ExceptionMiddleware)
    
    # 4. Authentication - MUST come before context and RLS
    app.add_middleware(
        JwtAuthMiddleware,
        algorithm=os.getenv("JWT_ALG", "HS256"),
        secret=os.getenv("JWT_SECRET"),
        required=False,  # Set to False to allow public endpoints
        issuer=os.getenv("JWT_ISSUER"),
        audience=os.getenv("JWT_AUDIENCE"),
        allow_anonymous_paths=[
            "/", "/docs", "/openapi.json",
            "/_health", "/_health/db", "/_health/redis",
            "/api/messaging/webhook",
            "/v1/wa/webhook"
            "/api/identity/auth",
            "/favicon.ico",            
        ],
    )
    
    # 5. Context binding (needs auth info from JWT middleware)
    app.add_middleware(ContextMiddleware)
    
    # 6. RLS enforcement (needs context from ContextMiddleware)
    app.add_middleware(RlsMiddleware)
    
    # 7. Rate limiting (needs tenant context)
    app.add_middleware(RateLimitMiddleware)
    
    # 8. Access logging (innermost - measures full stack)
    app.add_middleware(LoggingMiddleware)
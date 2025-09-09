from __future__ import annotations

from fastapi import FastAPI

from .security_middleware import SecurityHeadersMiddleware, IpAllowlistMiddleware
from .request_id_middleware import RequestIdMiddleware
from .exception_middleware import ExceptionMiddleware
from .jwt_auth_middleware import JwtAuthMiddleware
from .context_middleware import ContextMiddleware
from .rls_middleware import RlsContextEnforcerMiddleware
from .rate_limit_middleware import RateLimitMiddleware
from .logging_middleware import LoggingMiddleware

def setup_http_middlewares(app: FastAPI) -> None:
    """
    Install middlewares in correct order (outer → inner).
    """
    # 1) Security hardening
    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(IpAllowlistMiddleware, allowlist_cidrs=[], enabled=False)

    # 2) Correlation id (used by everything else)
    app.add_middleware(RequestIdMiddleware)

    # 3) Centralized exception translator (wraps below)
    app.add_middleware(ExceptionMiddleware)

    # 4) JWT auth → populates request.state.* (tid, sub, roles)
    #    Configure keys here (example HS256). For RS256, pass public_key_pem and algorithm="RS256".
    app.add_middleware(
        JwtAuthMiddleware,
        algorithm="HS256",
        secret="CHANGE_ME_SUPER_SECRET",    # <- pull from env in real app
        required=False,                     # flip True if you want all non-public paths authenticated
        issuer=None,
        audience=None,
        allow_anonymous_paths=[
            "/", "/docs", "/openapi.json",
            "/_health/db", "/_health/redis",
            "/api/messaging/webhook",
        ],
    )

    # 5) Bind identity to ctxvars + MDC
    app.add_middleware(ContextMiddleware)

    # 6) Enforce tenant context on tenant-scoped APIs
    app.add_middleware(RlsContextEnforcerMiddleware, public_paths=[
        "/", "/docs", "/openapi.json", "/_health/db", "/_health/redis", "/api/messaging/webhook",
    ])

    # 7) Per-tenant rate limit (no-op if Redis absent)
    app.add_middleware(RateLimitMiddleware)

    # 8) Structured access logging
    app.add_middleware(LoggingMiddleware)

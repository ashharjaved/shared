from __future__ import annotations

import logging
import uuid
from typing import Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from src.shared.database import tenant_ctx, user_ctx, roles_ctx
from src.shared.security import decode_jwt

logger = logging.getLogger("app")


class RequestContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Request ID for logs
        req_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
        # Attempt to parse JWT (if present) to prefill context
        tenant_id = None
        user_id = None
        role_val = None

        auth = request.headers.get("Authorization", "")
        if auth.startswith("Bearer "):
            token = auth.split(" ", 1)[1]
            try:
                claims = decode_jwt(token)
                tenant_id = claims.get("tenant_id")
                user_id = claims.get("sub")
                role_val = claims.get("role")
            except Exception:
                # Leave unauthenticated; route guards will raise
                pass

        token_t = tenant_ctx.set(tenant_id)
        token_u = user_ctx.set(user_id)
        token_r = roles_ctx.set(role_val)

        response = await call_next(request)
        response.headers["X-Request-ID"] = req_id

        tenant_ctx.reset(token_t)
        user_ctx.reset(token_u)
        roles_ctx.reset(token_r)
        return response

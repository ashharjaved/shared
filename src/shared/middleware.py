from __future__ import annotations
import time, uuid, logging
from typing import Callable
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

logger = logging.getLogger(__name__)

class LoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        request_id = str(uuid.uuid4())
        start = time.time()

        tenant_id = request.headers.get("X-Tenant-Id")
        user_id = None

        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            try:
                import jwt
                from ..config import settings
                token = auth_header.split(" ", 1)[1]
                payload = jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALG])
                tenant_id = payload.get("tenant_id", tenant_id)
                user_id = payload.get("sub")
            except Exception:
                pass  # ignore bad tokens for logging

        logger.info(
            "Request started",
            extra={"request_id": request_id, "method": request.method, "url": str(request.url),
                   "tenant_id": tenant_id, "user_id": user_id,
                   "user_agent": request.headers.get("User-Agent"),
                   "client_ip": request.client.host if request.client else None},
        )

        request.state.request_id = request_id
        request.state.tenant_id = tenant_id
        request.state.user_id = user_id

        try:
            response = await call_next(request)
            duration = time.time() - start
            logger.info("Request completed", extra={"request_id": request_id, "status_code": response.status_code,
                                                   "duration_ms": round(duration * 1000, 2),
                                                   "tenant_id": tenant_id, "user_id": user_id})
            response.headers["X-Request-ID"] = request_id
            return response
        except Exception as e:
            duration = time.time() - start
            logger.error("Request failed", extra={"request_id": request_id, "error": str(e),
                                                  "duration_ms": round(duration * 1000, 2),
                                                  "tenant_id": tenant_id, "user_id": user_id}, exc_info=True)
            raise

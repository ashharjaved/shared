# src/shared/middleware.py
from __future__ import annotations

import time
import uuid

from fastapi import Request
from starlette.types import ASGIApp, Receive, Scope, Send

from src.shared.logging import log_event
from src.config import get_settings

settings=get_settings()
class CorrelationIdMiddleware:
    """
    Ensures every request has a correlation id.
    - Reads from X-Correlation-ID if provided, otherwise generates one.
    - Exposes request.state.correlation_id for downstream usage.
    - Echoes X-Correlation-ID in response headers.
    """
    def __init__(self, app: ASGIApp, header_name: str = "X-Correlation-ID"):
        self.app = app
        self.header_name = header_name

    async def __call__(self, scope: Scope, receive: Receive, send: Send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request = Request(scope, receive=receive)
        corr = request.headers.get(self.header_name) or str(uuid.uuid4())
        request.state.correlation_id = corr

        async def send_wrapper(message):
            if message.get("type") == "http.response.start":
                headers = list(message.get("headers") or [])
                headers.append((self.header_name.encode(), corr.encode()))
                message["headers"] = headers
            await send(message)

        await self.app(scope, receive, send_wrapper)


class RequestLoggingMiddleware:
    """
    Lightweight request timing + structured logging.
    - Logs start/finish with method, path, status, duration_ms.
    - Adds ENV/SERVICE_NAME context for centralized log search.
    """
    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request = Request(scope, receive=receive)
        corr_id = getattr(request.state, "correlation_id", None)
        start = time.perf_counter()

        log_event(
            "HttpRequestStarted",
            correlation_id=corr_id,
            method=scope.get("method"),
            path=scope.get("path"),
            service="",
            env=settings.ENVIRONMENT,
        )

        async def send_wrapper(message):
            if message.get("type") == "http.response.start":
                status = message.get("status")
                duration_ms = int((time.perf_counter() - start) * 1000)
                log_event(
                    "HttpRequestCompleted",
                    correlation_id=corr_id,
                    method=scope.get("method"),
                    path=scope.get("path"),
                    status=status,
                    duration_ms=duration_ms,
                    service=settings.PROJECT_NAME,
                    env=settings.ENVIRONMENT,
                )
            await send(message)

        await self.app(scope, receive, send_wrapper)

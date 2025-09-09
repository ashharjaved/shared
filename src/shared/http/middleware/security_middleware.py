from __future__ import annotations

from ipaddress import ip_address, ip_network
from typing import Iterable, Optional
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response, PlainTextResponse

class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """
    Adds strict security headers on every response.
    """
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        response = await call_next(request)
        # Strict transport & anti-mime sniff
        response.headers.setdefault("Strict-Transport-Security", "max-age=63072000; includeSubDomains; preload")
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "no-referrer")
        response.headers.setdefault("Permissions-Policy", "geolocation=(), microphone=(), camera=()")
        return response

class IpAllowlistMiddleware(BaseHTTPMiddleware):
    """
    Optional allowlist for sensitive admin surfaces or webhooks.
    Example usage: only allow Meta/WhatsApp ranges on webhook if desired.
    """
    def __init__(self, app, allowlist_cidrs: Optional[Iterable[str]] = None, enabled: bool = False):
        super().__init__(app)
        self.enabled = enabled
        self.networks = [ip_network(cidr) for cidr in (allowlist_cidrs or [])]

    def _is_allowed(self, addr: Optional[str]) -> bool:
        if not self.enabled or not self.networks or not addr:
            return True
        try:
            ip = ip_address(addr)
            return any(ip in net for net in self.networks)
        except ValueError:
            return False

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        if not self.enabled:
            return await call_next(request)
        client_ip = request.client.host if request.client else None
        if not self._is_allowed(client_ip):
            return PlainTextResponse("Forbidden", status_code=403)
        return await call_next(request)

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
        
        # Security headers
        security_headers = {
            "Strict-Transport-Security": "max-age=63072000; includeSubDomains; preload",
            "X-Content-Type-Options": "nosniff",
            "X-Frame-Options": "DENY",
            "Referrer-Policy": "strict-origin-when-cross-origin",
            "Permissions-Policy": "geolocation=(), microphone=(), camera=()",
            "X-XSS-Protection": "1; mode=block",
        }
        
        for header, value in security_headers.items():
            response.headers.setdefault(header, value)
            
        return response

class IpAllowlistMiddleware(BaseHTTPMiddleware):
    """
    Optional allowlist for sensitive admin surfaces or webhooks.
    """
    
    def __init__(self, app, allowlist_cidrs: Optional[Iterable[str]] = None, enabled: bool = False):
        super().__init__(app)
        self.enabled = enabled
        self.networks = [ip_network(cidr) for cidr in (allowlist_cidrs or [])]

    def _is_allowed(self, addr: Optional[str]) -> bool:
        if not self.enabled or not self.networks or not addr:
            return True
        
        try:
            # Handle X-Forwarded-For headers
            if "," in addr:
                addr = addr.split(",")[0].strip()
                
            ip = ip_address(addr)
            return any(ip in net for net in self.networks)
        except ValueError:
            return False

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        if not self.enabled:
            return await call_next(request)
            
        client_ip = (
            request.headers.get("X-Forwarded-For") 
            or (request.client.host if request.client else None)
        )
        
        if not self._is_allowed(client_ip):
            return PlainTextResponse("Forbidden", status_code=403)
            
        return await call_next(request)
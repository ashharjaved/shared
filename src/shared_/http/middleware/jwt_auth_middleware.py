from __future__ import annotations

import base64
import json
import uuid
from typing import Callable, Optional, Sequence, Tuple

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response
from starlette.datastructures import State
from src.shared_.utils import tenant_ctxvars as ctxvars
from src.shared_.structured_logging import bind_request_context
from src.shared_.errors import UnauthorizedError

import hmac
import hashlib
import structlog
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.backends import default_backend

logger = structlog.get_logger()

def _b64url_decode(data: str) -> bytes:
    """Base64 URL-safe decode with padding."""
    pad = '=' * (-len(data) % 4)
    return base64.urlsafe_b64decode(data + pad)

def _jwt_parts(token: str) -> Tuple[dict, dict, bytes, bytes]:
    """Split and decode JWT parts."""
    try:
        h_b64, p_b64, s_b64 = token.split(".")
    except ValueError:
        raise UnauthorizedError(message="Invalid token format")
    
    try:
        header = json.loads(_b64url_decode(h_b64).decode("utf-8"))
        payload = json.loads(_b64url_decode(p_b64).decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise UnauthorizedError(message="Invalid token encoding")
    
    sig = _b64url_decode(s_b64)
    signing_input = f"{h_b64}.{p_b64}".encode("ascii")
    return header, payload, signing_input, sig

def _verify_hs256(signing_input: bytes, sig: bytes, secret: bytes) -> bool:
    """Verify HMAC-SHA256 signature."""
    expected = hmac.new(secret, signing_input, hashlib.sha256).digest()
    return hmac.compare_digest(expected, sig)

def _verify_rs256(signing_input: bytes, sig: bytes, public_pem: str) -> bool:
    """Verify RSA-SHA256 signature."""
    try:
        public_key = serialization.load_pem_public_key(
            public_pem.encode("utf-8"), 
            backend=default_backend()
        )
        
        if not isinstance(public_key, rsa.RSAPublicKey):
            return False
            
        public_key.verify(
            sig, 
            signing_input, 
            padding.PKCS1v15(), 
            hashes.SHA256()
        )
        return True
    except Exception:
        return False

def _extract_bearer(auth_header: Optional[str]) -> Optional[str]:
    """Extract Bearer token from Authorization header."""
    if not auth_header:
        return None
    
    prefix = "Bearer "
    if auth_header.startswith(prefix):
        return auth_header[len(prefix):].strip()
    
    return None

class JwtAuthMiddleware(BaseHTTPMiddleware):
    """
    Verifies JWT (HS256 or RS256) and places claims into request.state.
    """

    def __init__(
        self,
        app,
        *,
        algorithm: str = "HS256",
        secret: Optional[str] = None,
        public_key_pem: Optional[str] = None,
        required: bool = False,
        issuer: Optional[str] = None,
        audience: Optional[str] = None,
        auth_header: str = "Authorization",
        allow_anonymous_paths: Optional[Sequence[str]] = None,
        extra_validator: Optional[Callable[[dict], None]] = None,
    ):
        super().__init__(app)
        self.algorithm = algorithm.upper()
        self._secret = secret.encode("utf-8") if secret and self.algorithm == "HS256" else None
        self.public_key_pem = public_key_pem if self.algorithm == "RS256" else None
        self.required = required
        self.issuer = issuer
        self.audience = audience
        self.auth_header = auth_header
        self.allow_anonymous_paths = set(allow_anonymous_paths or [
            "/", "/docs", "/openapi.json", "/_health/db", 
            "/_health/redis", "/api/messaging/webhook","/v1/wa/webhook"
        ])
        self.extra_validator = extra_validator

        if self.algorithm not in {"HS256", "RS256"}:
            raise ValueError("Unsupported JWT algorithm")
        if self.algorithm == "HS256" and not self._secret:
            raise ValueError("HS256 requires `secret`")
        if self.algorithm == "RS256" and not self.public_key_pem:
            raise ValueError("RS256 requires `public_key_pem`")

    def _validate_claims(self, payload: dict) -> None:
        """Validate JWT claims."""
        if self.issuer and payload.get("iss") != self.issuer:
            raise UnauthorizedError(message="Invalid issuer")
        
        if self.audience:
            aud = payload.get("aud")
            if isinstance(aud, str):
                ok = aud == self.audience
            elif isinstance(aud, list):
                ok = self.audience in aud
            else:
                ok = False
            if not ok:
                raise UnauthorizedError(message="Invalid audience")
        
        if self.extra_validator:
            self.extra_validator(payload)

    def _parse_roles(self, payload: dict) -> list[str]:
        """Parse roles from JWT payload."""
        roles = payload.get("roles")
        if roles is None:
            return []
        if isinstance(roles, list):
            return [str(r).strip() for r in roles if str(r).strip()]
        if isinstance(roles, str):
            return [r.strip() for r in roles.split(",") if r.strip()]
        return []

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        path = request.url.path
        is_public = any(path == p or path.startswith(p.rstrip("/") + "/") for p in self.allow_anonymous_paths)

        token = _extract_bearer(request.headers.get(self.auth_header))
        if not token and is_public:
            return await call_next(request)
        if not token and self.required:
            raise UnauthorizedError(message="Missing bearer token")
        if not token:
            return await call_next(request)

        header, payload, signing_input, sig = _jwt_parts(token)
        alg = header.get("alg", "").upper()
        if alg != self.algorithm:
            raise UnauthorizedError(message="Algorithm mismatch")
        
        if self.algorithm == "HS256":
            assert self._secret is not None
            verified = _verify_hs256(signing_input, sig, self._secret)
        else:
            verified = _verify_rs256(signing_input, sig, self.public_key_pem or "")
        if not verified:
            raise UnauthorizedError(message="Invalid token signature")

        self._validate_claims(payload)

        uid = str(payload.get("sub") or payload.get("uid") or "")
        tid = str(payload.get("tid") or payload.get("tenant_id") or "")
        role = str(payload.get("role") or payload.get("roles") or "")
        roles_list = self._parse_roles(payload)

        # Set attributes directly on request.state
        request.state.user_id = uid
        request.state.tenant_id = tid
        request.state.roles_csv = ",".join(roles_list)
        request.state.user_claims = payload
        request.state.roles = roles_list

        # 2) Bind ctxvars (this is what AsyncUoW/session_from_ctxvars rely on)
        ctxvars.set_all(
            tenant_id=tid,
            user_id=uid,
            roles=[role] if role else [],  # list ok; tenant_context_from_ctxvars handles both list/CSV
            request_id=getattr(request.state, "request_id", None),
        )

        # 3) Bind into log MDC so every log line shows them
        bind_request_context(
            request_id=getattr(request.state, "request_id", "") or "",
            tenant_id=tid or "",
            user_id=uid or "",
            roles=role,
        )
        logger.debug("jwt_authenticated", user_id=uid, tenant_id=tid, roles=role)
        return await call_next(request)
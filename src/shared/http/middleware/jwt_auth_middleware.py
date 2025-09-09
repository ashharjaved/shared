from __future__ import annotations

import base64
import json
from typing import Callable, Optional, Sequence, Tuple

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response
from starlette.status import HTTP_401_UNAUTHORIZED, HTTP_403_FORBIDDEN

from src.shared.errors import UnauthorizedError, AuthorizationError

# ---- minimal, dependency-free JWT verifier ----
# - Supports HS256 (shared secret) and RS256 (PEM public key)
# - Constant-time comparisons avoided here for brevity; you can extend if needed

import hmac
import hashlib

def _b64url_decode(data: str) -> bytes:
    pad = '=' * (-len(data) % 4)
    return base64.urlsafe_b64decode(data + pad)

def _jwt_parts(token: str) -> Tuple[dict, dict, bytes, bytes]:
    try:
        h_b64, p_b64, s_b64 = token.split(".")
    except ValueError:
        raise UnauthorizedError(message="Invalid token format")
    header = json.loads(_b64url_decode(h_b64).decode("utf-8"))
    payload = json.loads(_b64url_decode(p_b64).decode("utf-8"))
    sig = _b64url_decode(s_b64)
    signing_input = f"{h_b64}.{p_b64}".encode("ascii")
    return header, payload, signing_input, sig

def _verify_hs256(signing_input: bytes, sig: bytes, secret: bytes) -> bool:
    expected = hmac.new(secret, signing_input, hashlib.sha256).digest()
    return hmac.compare_digest(expected, sig)

# Lazy optional import (avoid hard dep if RS256 unused)
def _load_pem_public_key(pem: str):
    try:
        from cryptography.hazmat.primitives import serialization
        from cryptography.hazmat.backends import default_backend
    except Exception as e:  # pragma: no cover
        raise UnauthorizedError(message="cryptography not installed for RS256") from e
    return serialization.load_pem_public_key(pem.encode("utf-8"), backend=default_backend())

def _verify_rs256(signing_input: bytes, sig: bytes, public_pem: str) -> bool:
    try:
        from cryptography.hazmat.primitives.asymmetric import padding
        from cryptography.hazmat.primitives import hashes
        pub = _load_pem_public_key(public_pem)
        pub.verify(sig, signing_input, padding.PKCS1v15(), hashes.SHA256())
        return True
    except Exception:
        return False

def _extract_bearer(auth_header: Optional[str]) -> Optional[str]:
    if not auth_header:
        return None
    prefix = "Bearer "
    return auth_header[len(prefix):].strip() if auth_header.startswith(prefix) else None

class JwtAuthMiddleware(BaseHTTPMiddleware):
    """
    Verifies JWT (HS256 or RS256) and places claims into request.state:
      - tenant_id: payload["tid"] or payload["tenant_id"]
      - user_id:   payload["sub"] or payload["uid"]
      - roles:     payload["roles"] (list[str]) or CSV string
    This middleware **does not** enforce RBAC; it only authenticates and populates claims.
    Pair with your Context/RLS middlewares + route-level guards.
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
        self.secret = secret.encode("utf-8") if secret and self.algorithm == "HS256" else None
        self.public_key_pem = public_key_pem if self.algorithm == "RS256" else None
        self.required = required
        self.issuer = issuer
        self.audience = audience
        self.auth_header = auth_header
        self.allow_anonymous_paths = set(allow_anonymous_paths or ["/", "/docs", "/openapi.json", "/_health/db", "/_health/redis", "/api/messaging/webhook"])
        self.extra_validator = extra_validator

        if self.algorithm not in {"HS256", "RS256"}:
            raise ValueError("Unsupported JWT algorithm")
        if self.algorithm == "HS256" and not self.secret:
            raise ValueError("HS256 requires `secret`")
        if self.algorithm == "RS256" and not self.public_key_pem:
            raise ValueError("RS256 requires `public_key_pem`")

    def _validate_claims(self, payload: dict) -> None:
        # Optional iss/aud checks
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
        # User hook for additional checks (exp/nbf/iats or custom logic)
        if self.extra_validator:
            self.extra_validator(payload)

    def _parse_roles(self, payload: dict) -> list[str]:
        roles = payload.get("roles")
        if roles is None:
            return []
        if isinstance(roles, list):
            return [str(r) for r in roles if str(r).strip()]
        if isinstance(roles, str):
            return [r.strip() for r in roles.split(",") if r.strip()]
        return []

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        # allow anonymous paths (health/docs/webhook verify) even if required=True
        path = request.url.path
        if any(path == p or path.startswith(p.rstrip("/") + "/") for p in self.allow_anonymous_paths):
            return await call_next(request)

        token = _extract_bearer(request.headers.get(self.auth_header))
        if not token:
            if self.required:
                # Short-circuit here; ExceptionMiddleware will format
                raise UnauthorizedError(message="Missing bearer token")
            return await call_next(request)

        header, payload, signing_input, sig = _jwt_parts(token)

        alg = header.get("alg", "").upper()
        if alg != self.algorithm:
            raise UnauthorizedError(message="Algorithm mismatch")

        verified = (
            _verify_hs256(signing_input, sig, self.secret) if self.algorithm == "HS256"
            else _verify_rs256(signing_input, sig, self.public_key_pem or "")
        )
        if not verified:
            raise UnauthorizedError(message="Invalid token signature")

        # claim checks (iss, aud, exp/nbf via extra_validator, etc.)
        self._validate_claims(payload)

        # map claims to request.state for downstream middlewares
        request.state.user_id = str(payload.get("sub") or payload.get("uid") or "")
        request.state.tenant_id = str(payload.get("tid") or payload.get("tenant_id") or "")
        request.state.roles_csv = ",".join(self._parse_roles(payload))

        return await call_next(request)

# src/shared/security.py
from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from datetime import datetime, timedelta, timezone
from typing import Any, Dict

import jwt  # PyJWT
from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from passlib.context import CryptContext
from passlib.hash import argon2, bcrypt
from uuid import UUID

from src.config import get_settings
from src.identity.domain.value_objects import Role
from src.shared.exceptions import ForbiddenError, UnauthorizedError

logger = logging.getLogger("app.security")

# -----------------------------------------------------------------------------
# Password hashing (Argon2id preferred; bcrypt fallback)
# -----------------------------------------------------------------------------
_pwd_ctx = CryptContext(
    schemes=["argon2", "bcrypt"],
    deprecated="auto",
)

def hash_password(plain: str) -> str:
    """Hash a password with argon2id (preferred) or bcrypt (fallback)."""
    return _pwd_ctx.hash(plain)

def verify_password(plain: str, hashed: str) -> bool:
    """Verify password against a hash (supports argon2/bcrypt)."""
    return _pwd_ctx.verify(plain, hashed)

# Optional typed hasher abstraction (kept as in your file)
class PasswordHasher(ABC):
    @abstractmethod
    def hash(self, password: str) -> str: ...
    @abstractmethod
    def verify(self, password: str, hashed: str) -> bool: ...

class Argon2PasswordHasher(PasswordHasher):
    def hash(self, password: str) -> str:
        return argon2.using(rounds=4).hash(password)  # Argon2id
    def verify(self, password: str, hashed: str) -> bool:
        try:
            return argon2.verify(password, hashed)
        except Exception:
            return False

class BcryptPasswordHasher(PasswordHasher):
    def hash(self, password: str) -> str:
        return bcrypt.using(rounds=12).hash(password)
    def verify(self, password: str, hashed: str) -> bool:
        try:
            return bcrypt.verify(password, hashed)
        except Exception:
            return False

def get_password_hasher() -> PasswordHasher:
    """Factory driven by settings.PASSWORD_HASH_SCHEME."""
    scheme = get_settings().PASSWORD_HASH_SCHEME.lower()
    return Argon2PasswordHasher() if scheme == "argon2" else BcryptPasswordHasher()

# -----------------------------------------------------------------------------
# JWT helpers (HS256 by default) — payload: {sub, tenant_id, role, iat, exp}
# -----------------------------------------------------------------------------
def _now_utc() -> datetime:
    return datetime.now(timezone.utc)

def encode_jwt(
    *,
    sub: str,
    tenant_id: str,
    role: str,
    expires_minutes: int | None = None,
    extra_claims: Dict[str, Any] | None = None,
) -> str:
    settings = get_settings()
    alg = settings.JWT_ALG
    exp_minutes = expires_minutes if expires_minutes is not None else settings.JWT_EXPIRE_MINUTES

    now = _now_utc()
    payload: Dict[str, Any] = {
        "sub": sub,
        "tenant_id": tenant_id,
        "role": role,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=exp_minutes)).timestamp()),
    }
    if extra_claims:
        for k, v in extra_claims.items():
            if k not in {"sub", "tenant_id", "role", "iat", "exp"}:
                payload[k] = v

    return jwt.encode(payload, settings.JWT_SECRET, algorithm=alg)

def decode_jwt(token: str) -> Dict[str, Any]:
    settings = get_settings()
    payload = jwt.decode(
        token,
        settings.JWT_SECRET,
        algorithms=[settings.JWT_ALG],
        options={"require": ["sub", "tenant_id", "role", "exp", "iat"]},
    )
    if not isinstance(payload.get("sub"), str):
        raise jwt.InvalidTokenError("Invalid 'sub' claim")
    if not isinstance(payload.get("tenant_id"), str):
        raise jwt.InvalidTokenError("Invalid 'tenant_id' claim")
    if not isinstance(payload.get("role"), str):
        raise jwt.InvalidTokenError("Invalid 'role' claim")
    return payload

# -----------------------------------------------------------------------------
# Token Provider abstraction
# -----------------------------------------------------------------------------
class TokenProvider(ABC):
    @abstractmethod
    def encode(self, *, sub: UUID, tenant_id: UUID, role: Role) -> str: ...
    @abstractmethod
    def decode(self, token: str) -> dict[str, Any]: ...

class JWTTokenProvider(TokenProvider):
    def __init__(self):
        self.settings = get_settings()

    def encode(self, *, sub: UUID, tenant_id: UUID, role: Role) -> str:
        now = _now_utc()
        exp = now + timedelta(minutes=self.settings.JWT_EXPIRE_MINUTES)
        payload = {
            "sub": str(sub),
            "tenant_id": str(tenant_id),
            "role": role.value,
            "iat": int(now.timestamp()),
            "exp": int(exp.timestamp()),
        }
        return jwt.encode(payload, self.settings.JWT_SECRET, algorithm=self.settings.JWT_ALG)

    def decode(self, token: str) -> dict[str, Any]:
        try:
            return jwt.decode(token, self.settings.JWT_SECRET, algorithms=[self.settings.JWT_ALG])
        except jwt.ExpiredSignatureError as e:
            raise UnauthorizedError("Token expired") from e
        except jwt.InvalidTokenError as e:
            raise UnauthorizedError("Invalid token") from e

def get_token_provider() -> TokenProvider:
    return JWTTokenProvider()

# -----------------------------------------------------------------------------
# FastAPI dependencies
# -----------------------------------------------------------------------------
_bearer = HTTPBearer(auto_error=False)

async def auth_credentials(creds: HTTPAuthorizationCredentials | None = Depends(_bearer)) -> dict | None:
    if not creds:
        return None
    provider = get_token_provider()
    return provider.decode(creds.credentials)

def require_auth(jwt_claims: dict | None = Depends(auth_credentials)) -> dict:
    if not jwt_claims:
        raise UnauthorizedError("Missing or invalid Authorization header")
    return jwt_claims

def require_roles(*allowed: Role):
    async def _dep(jwt_claims: dict = Depends(require_auth)) -> dict:
        role = jwt_claims.get("role")
        if role not in [r.value for r in allowed]:
            raise ForbiddenError("Insufficient role")
        return jwt_claims
    return _dep
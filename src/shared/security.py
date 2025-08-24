from __future__ import annotations
from abc import ABC, abstractmethod
import logging
from typing import Any
import datetime as dt
import jwt  # PyJWT
from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from passlib.hash import argon2, bcrypt
from sqlalchemy import UUID

from src.identity.domain.value_objects import Role
from src.config import get_settings
from src.shared.exceptions import InvalidCredentialsError, UnauthorizedError, ForbiddenError

logger = logging.getLogger("app.security")

# ==========================================================
# Abstraction: PasswordHasher
# ==========================================================
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
    if scheme == "argon2":
        return Argon2PasswordHasher()
    return BcryptPasswordHasher()


# ==========================================================
# Abstraction: TokenProvider
# ==========================================================
class TokenProvider(ABC):
    @abstractmethod
    def encode(self, *, sub: UUID, tenant_id: UUID, role: Role) -> str: ...

    @abstractmethod
    def decode(self, token: str) -> dict[str, Any]: ...


class JWTTokenProvider(TokenProvider):
    def __init__(self):
        self.settings = get_settings()

    def encode(self, *, sub: UUID, tenant_id: UUID, role: Role) -> str:
        now = dt.datetime.utcnow()
        exp = now + dt.timedelta(minutes=self.settings.JWT_EXPIRES_MIN)
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


# ==========================================================
# FastAPI Dependencies
# ==========================================================
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

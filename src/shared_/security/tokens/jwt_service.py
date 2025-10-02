from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Dict, Optional, Union
from uuid import UUID
import jwt  # PyJWT
from .ports import TokenServicePort  # protocol

@dataclass(frozen=True)
class TokenSettings:
    algorithm: str
    access_minutes: int = 60
    refresh_days: int = 7
    private_key: Optional[str] = None
    public_key: Optional[str] = None
    secret: Optional[str] = None

    def signing_key(self) -> Any:
        return self.private_key if self.algorithm == "RS256" else self.secret

    def verify_key(self) -> Any:
        return self.public_key if self.algorithm == "RS256" else self.secret

class TokenService(TokenServicePort):
    def __init__(self, settings: TokenSettings) -> None:
        self._s = settings

    def _now(self) -> datetime:
        return datetime.utcnow()

    def _encode(self, payload: Dict[str, Any]) -> str:
        return jwt.encode(payload, self._s.signing_key(), algorithm=self._s.algorithm)

    def create_access(self, sub: Union[str, UUID], tenant_id: Union[str, UUID], role: str,
                      expires: Optional[timedelta] = None) -> str:
        exp = self._now() + (expires or timedelta(minutes=self._s.access_minutes))
        payload = {"sub": str(sub), "tenant_id": str(tenant_id), "role": role,
                   "iat": int(self._now().timestamp()), "exp": int(exp.timestamp()), "typ": "access"}
        return self._encode(payload)

    def create_refresh(self, sub: Union[str, UUID], tenant_id: Union[str, UUID], role: str,
                       expires: Optional[timedelta] = None) -> str:
        exp = self._now() + (expires or timedelta(days=self._s.refresh_days))
        payload = {"sub": str(sub), "tenant_id": str(tenant_id), "role": role,
                   "iat": int(self._now().timestamp()), "exp": int(exp.timestamp()), "typ": "refresh"}
        return self._encode(payload)

    def decode(self, token: str) -> Dict[str, Any]:
        try:
            return jwt.decode(token, self._s.verify_key(),
                              algorithms=[self._s.algorithm], options={"verify_exp": True})
        except jwt.ExpiredSignatureError as e:
            raise ValueError("Token has expired") from e
        except jwt.InvalidTokenError as e:
            raise ValueError(f"Invalid token: {e}") from e

from __future__ import annotations
from typing import Optional, Union, Dict, Any
from uuid import UUID
from datetime import timedelta
from src.shared_.utils.crypto import CryptoUtils
from src.shared_.security.passwords.factory import build_password_hasher
from src.shared_.security.tokens.jwt_service import TokenService, TokenSettings
from src.shared_.security.secretbox.fernet_box import SecretBox
from src.shared_.security.secretbox.ports import SecretBoxPort

class SecuritySuite:
    def __init__(self, token_settings: TokenSettings, secretbox: bool = True) -> None:
        self.crypto = CryptoUtils()
        self.passwords = build_password_hasher()
        self.tokens = TokenService(token_settings)
        self.secrets: Optional[SecretBoxPort] = SecretBox() if secretbox else None

    def hash_password(self, plain: str) -> str:
        return self.passwords.hash(plain)

    def verify_password(self, plain: str, hashed: str) -> bool:
        return self.passwords.verify(plain, hashed)

    def create_access_token(self, sub: Union[str, UUID], tenant_id: Union[str, UUID], role: str,
                            expires: Optional[timedelta] = None) -> str:
        return self.tokens.create_access(sub, tenant_id, role, expires)

    def create_refresh_token(self, sub: Union[str, UUID], tenant_id: Union[str, UUID], role: str,
                             expires: Optional[timedelta] = None) -> str:
        return self.tokens.create_refresh(sub, tenant_id, role, expires)

    def decode_token(self, token: str) -> Dict[str, Any]:
        return self.tokens.decode(token)

    def encrypt(self, plain: str) -> str:
        if not self.secrets:
            raise RuntimeError("SecretBox not configured")
        return self.secrets.encrypt(plain)

    def decrypt(self, cipher: str) -> str:
        if not self.secrets:
            raise RuntimeError("SecretBox not configured")
        return self.secrets.decrypt(cipher)

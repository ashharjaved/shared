from __future__ import annotations
import os
from cryptography.fernet import Fernet, InvalidToken
from .ports import SecretBoxPort
from dotenv import load_dotenv
load_dotenv()
class SecretBox(SecretBoxPort):
    def __init__(self, key_env: str = "APP_ENCRYPTION_KEY") -> None:
        enc_key = os.getenv(key_env)
        if not enc_key:
            raise RuntimeError(f"{key_env} not set in environment")
        self._fernet = Fernet(enc_key.encode())

    def encrypt(self, plain: str) -> str:
        return self._fernet.encrypt(plain.encode()).decode()

    def decrypt(self, cipher: str) -> str:
        try:
            return self._fernet.decrypt(cipher.encode()).decode()
        except InvalidToken as e:
            raise ValueError("Decryption failed – invalid key or corrupted data") from e

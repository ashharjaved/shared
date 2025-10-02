from __future__ import annotations
import hashlib, hmac
from typing import Union

class CryptoUtils:
    @staticmethod
    def sha256_hex(data: Union[bytes, str]) -> str:
        if isinstance(data, str):
            data = data.encode("utf-8")
        return hashlib.sha256(data).hexdigest()

    @staticmethod
    def hmac_sha256_hex(key: Union[bytes, str], data: Union[bytes, str]) -> str:
        if isinstance(key, str):
            key = key.encode("utf-8")
        if isinstance(data, str):
            data = data.encode("utf-8")
        return hmac.new(key, data, hashlib.sha256).hexdigest()

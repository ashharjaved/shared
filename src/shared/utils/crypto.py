# /src/shared/utils/crypto.py
"""
Crypto helpers. No secrets logged.

- sha256_hex(data)
- hmac_sha256_hex(key, data)
- password_hash(password)  -> uses argon2 or bcrypt if available, else PBKDF2 fallback
- password_verify(password, hashed) -> bool
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import os
from typing import Optional

# --------- basic digests --------------------------------------------------------------

def sha256_hex(data: bytes | str) -> str:
    if isinstance(data, str):
        data = data.encode("utf-8")
    return hashlib.sha256(data).hexdigest()

def hmac_sha256_hex(key: bytes | str, data: bytes | str) -> str:
    if isinstance(key, str):
        key = key.encode("utf-8")
    if isinstance(data, str):
        data = data.encode("utf-8")
    return hmac.new(key, data, hashlib.sha256).hexdigest()

# --------- password hashing (pluggable) -----------------------------------------------

_HAS_ARGON2 = False
_HAS_BCRYPT = False

try:
    from argon2 import PasswordHasher  # type: ignore
    _argon2 = PasswordHasher()
    _HAS_ARGON2 = True
except Exception:
    _argon2 = None

if not _HAS_ARGON2:
    try:
        import bcrypt  # type: ignore
        _HAS_BCRYPT = True
    except Exception:
        pass

def password_hash(password: str) -> str:
    if _HAS_ARGON2 and _argon2:
        return _argon2.hash(password)
    if _HAS_BCRYPT:
        import bcrypt  # type: ignore
        salt = bcrypt.gensalt()
        return bcrypt.hashpw(password.encode("utf-8"), salt).decode("utf-8")
    # PBKDF2 fallback (dev only)
    salt = os.urandom(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 100_000)
    return "pbkdf2$" + base64.b64encode(salt + dk).decode("utf-8")

def password_verify(password: str, hashed: str) -> bool:
    try:
        if hashed.startswith("$argon2"):
            if not _HAS_ARGON2 or not _argon2:
                return False
            _argon2.verify(hashed, password)
            return True
        if hashed.startswith("$2b$") or hashed.startswith("$2a$"):
            if not _HAS_BCRYPT:
                return False
            import bcrypt  # type: ignore
            return bcrypt.checkpw(password.encode("utf-8"), hashed.encode("utf-8"))
        if hashed.startswith("pbkdf2$"):
            raw = base64.b64decode(hashed.split("$", 1)[1])
            salt, dk = raw[:16], raw[16:]
            check = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 100_000)
            return hmac.compare_digest(dk, check)
    except Exception:
        return False
    return False

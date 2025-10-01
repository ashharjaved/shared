from __future__ import annotations
import importlib
from .ports import PasswordHasherPort

def build_password_hasher() -> PasswordHasherPort:
    try:
        importlib.import_module("passlib")
        from .passlib_hasher import PasslibPasswordHasher
        return PasslibPasswordHasher()
    except ImportError:
        from .pbkdf2_fallback import PBKDF2FallbackHasher
        return PBKDF2FallbackHasher()
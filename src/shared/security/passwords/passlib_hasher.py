from __future__ import annotations
import structlog
from passlib.context import CryptContext
from .ports import PasswordHasherPort

logger = structlog.get_logger(__name__)

class PasslibPasswordHasher(PasswordHasherPort):
    def __init__(self) -> None:
        # CryptContext is not strictly required by our verify path, but keep it configured.
        try:
            self._ctx = CryptContext(
                schemes=["argon2", "bcrypt"],
                deprecated="auto",
                argon2__type="ID",
                argon2__memory_cost=65536,
                argon2__time_cost=3,
                argon2__parallelism=4,
            )
        except Exception as e:
            logger.warning("Argon2 not available; falling back to bcrypt: %s", e)
            self._ctx = CryptContext(schemes=["bcrypt"], deprecated="auto")

        # Ensure these attributes always exist (we use them directly in hash/verify)
        try:
            from passlib.hash import argon2, bcrypt  # type: ignore
            self._argon2 = argon2.using(type="ID", memory_cost=65536, time_cost=3, parallelism=4)
            self._bcrypt = bcrypt
            self._has_argon2 = True
        except Exception as e:  # noqa: BLE001
            logger.warning("Argon2 not available; falling back to bcrypt", error=str(e))
            self._argon2 = None
            try:
                from passlib.hash import bcrypt  # type: ignore
                self._bcrypt = bcrypt
            except Exception as be:  # noqa: BLE001
                logger.error("passlib bcrypt not available", error=str(be))
                self._bcrypt = None
            self._has_argon2 = False

    def __post_init__(self) -> None:
        # Lazy import so module remains importable even if passlib is missing.
        try:
            from passlib.hash import argon2, bcrypt  # type: ignore
            self._argon2 = argon2.using(type="ID", memory_cost=65536, time_cost=3, parallelism=4)
            self._bcrypt = bcrypt
            self._has_argon2 = True
        except Exception as e:  # noqa: BLE001
            logger.warning("Argon2 not available; falling back to bcrypt", error=str(e))
            self._argon2 = None
            try:
                from passlib.hash import bcrypt  # type: ignore
                self._bcrypt = bcrypt
            except Exception as be:  # noqa: BLE001
                # If even bcrypt is unavailable, we will raise on use
                logger.error("passlib bcrypt not available", error=str(be))
                self._bcrypt = None
            self._has_argon2 = False

    def hash(self, plain: str) -> str:
        if not plain:
            raise ValueError("password_empty")
        # Prefer Argon2id
        if getattr(self, "_has_argon2", False) and self._argon2 is not None:
            return self._argon2.hash(plain)  # type: ignore[attr-defined]
        # Fallback to bcrypt
        if self._bcrypt is not None:
            return self._bcrypt.hash(plain)  # type: ignore[attr-defined]
        # Ultimate fallback (should not happen if passlib installed)
        logger.error("No passlib hashers available")
        raise RuntimeError("no_passlib_hashers_available")

    def verify(self, plain: str, hashed: str) -> bool:
        try:
            # Pick verifier based on hash prefix to avoid mismatches
            if hashed.startswith("$argon2"):
                if getattr(self, "_has_argon2", False) and self._argon2 is not None:
                    return self._argon2.verify(plain, hashed)  # type: ignore[attr-defined]
                logger.warning("Argon2 hash present but argon2 not available")
                return False
            if hashed.startswith("$2a$") or hashed.startswith("$2b$") or hashed.startswith("$2y$"):
                if self._bcrypt is not None:
                    return self._bcrypt.verify(plain, hashed)  # type: ignore[attr-defined]
                logger.warning("BCrypt hash present but bcrypt not available")
                return False
            # Unknown scheme: try argon2 then bcrypt
            if getattr(self, "_has_argon2", False) and self._argon2 is not None:
                return self._argon2.verify(plain, hashed)  # type: ignore[attr-defined]
            if self._bcrypt is not None:
                return self._bcrypt.verify(plain, hashed)  # type: ignore[attr-defined]
            logger.error("No passlib hashers available for verification")
            return False
        except Exception as e:  # noqa: BLE001
            logger.error("Password verification error", error=str(e))
            return False

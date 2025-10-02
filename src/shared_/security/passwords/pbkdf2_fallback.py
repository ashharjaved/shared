from __future__ import annotations
import base64, hashlib, hmac, os

import structlog
from .ports import PasswordHasherPort

logger = structlog.get_logger(__name__)

class PBKDF2FallbackHasher(PasswordHasherPort):
    iterations: int = 390_000
    dklen: int = 32

    def hash(self, plain: str) -> str:
        if not plain:
            # Respect error contract at service boundary; keep ValueError here and
            # let the application layer map to InvalidRequestError for HTTP.
        # (We avoid importing project exceptions to keep this module standalone.)
            raise ValueError("password_empty")
        import os, base64, hashlib, hmac
        salt = os.urandom(16)
        dk = hashlib.pbkdf2_hmac("sha256", plain.encode("utf-8"), salt, self.iterations, dklen=self.dklen)
        payload = b"|".join([
            b"pbkdf2",
            str(self.iterations).encode(),
            base64.urlsafe_b64encode(salt),
            base64.urlsafe_b64encode(dk),
        ])
        return payload.decode("ascii")

    def verify(self, plain: str, hashed: str) -> bool:
        import base64, hashlib, hmac
        try:
            algo, iters_str, salt_b64, dk_b64 = hashed.split("|", 3)
            if algo != "pbkdf2":
                logger.warning("PBKDF2 verify received non-pbkdf2 hash", algo=algo)
                return False
            iterations = int(iters_str)
            salt = base64.urlsafe_b64decode(salt_b64.encode("ascii"))
            expected = base64.urlsafe_b64decode(dk_b64.encode("ascii"))
            candidate = hashlib.pbkdf2_hmac("sha256", plain.encode("utf-8"), salt, iterations, dklen=len(expected))
            return hmac.compare_digest(candidate, expected)
        except Exception as e:  # noqa: BLE001
            logger.error("PBKDF2 verify failed", error=str(e))
            return False

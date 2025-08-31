from __future__ import annotations

import base64
import os
from dataclasses import dataclass
from typing import Dict

from src.shared.exceptions import CryptoError


@dataclass(frozen=True, slots=True)
class CryptoEnvelope:
    """
    Serialized ciphertext bundle for storage in JSONB.
    Fields:
      - v: version (for future rotation)
      - alg: algorithm hint
      - iv: base64url(nonce)
      - ct: base64url(ciphertext)
    """
    v: int
    alg: str
    iv: str
    ct: str

    def to_json(self) -> Dict:
        return {"v": self.v, "alg": self.alg, "iv": self.iv, "ct": self.ct}


class CryptoService:
    """
    AES-256-GCM envelope encryption using a single KEK from env.
    Requires `cryptography` to be installed. If not installed, raises a clear error.

    ENV:
      PLATFORM_CRYPTO_MASTER_KEY = base64url-encoded 32-byte key (AES-256)
    """
    ALG = "AES-256-GCM"

    def __init__(self) -> None:
        try:
            from cryptography.hazmat.primitives.ciphers.aead import AESGCM  # type: ignore
        except Exception as exc:  # pragma: no cover - import-time check
            raise CryptoError(
                "cryptography is required for AES-256-GCM. "
                "Install with `pip install cryptography`."
            ) from exc

        key_b64 = os.getenv("PLATFORM_CRYPTO_MASTER_KEY")
        if not key_b64:
            raise CryptoError("Missing PLATFORM_CRYPTO_MASTER_KEY env var (base64url-encoded 32-byte key).")
        try:
            key = base64.urlsafe_b64decode(key_b64 + "==")
        except Exception as exc:
            raise CryptoError("Invalid PLATFORM_CRYPTO_MASTER_KEY encoding.") from exc

        if len(key) != 32:
            raise CryptoError("PLATFORM_CRYPTO_MASTER_KEY must decode to 32 bytes (AES-256).")

        self._AESGCM = __import__("cryptography.hazmat.primitives.ciphers.aead", fromlist=["AESGCM"]).AESGCM
        self._kek = key

    def encrypt(self, plaintext_json: Dict) -> Dict:
        """
        Encrypt a JSON value; returns an envelope object to be stored in DB JSONB.
        """
        import json, os
        aes = self._AESGCM(self._kek)
        iv = os.urandom(12)
        pt = json.dumps(plaintext_json, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
        ct = aes.encrypt(iv, pt, associated_data=None)
        env = CryptoEnvelope(
            v=1,
            alg=self.ALG,
            iv=base64.urlsafe_b64encode(iv).decode("ascii").rstrip("="),
            ct=base64.urlsafe_b64encode(ct).decode("ascii").rstrip("="),
        )
        return env.to_json()

    def decrypt(self, envelope_json: Dict) -> Dict:
        """
        Decrypt an envelope produced by `encrypt`. Returns a JSON object.
        """
        import json
        try:
            if str(envelope_json.get("alg")) != self.ALG:
                raise CryptoError("Unsupported algorithm in envelope.")
            iv = base64.urlsafe_b64decode(envelope_json["iv"] + "==")
            ct = base64.urlsafe_b64decode(envelope_json["ct"] + "==")
        except Exception as exc:
            raise CryptoError("Malformed envelope.") from exc

        aes = self._AESGCM(self._kek)
        try:
            pt = aes.decrypt(iv, ct, associated_data=None)
        except Exception as exc:
            raise CryptoError("Decryption failed.") from exc

        return __import__("json").loads(pt.decode("utf-8"))

    @staticmethod
    def redact_marker() -> Dict:
        """
        Returns a standardized redaction marker suitable for API responses/lists.
        Secrets are not revealed; callers can indicate presence with has_value=true.
        """
        return {"redacted": True, "has_value": True}

"""
Encryption Utilities
AES-256 envelope encryption and key management placeholders
"""
from __future__ import annotations

import base64
import hashlib
import secrets
from typing import Any

from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

from shared.infrastructure.observability.logger import get_logger

logger = get_logger(__name__)


class EncryptionManager:
    """
    Manages encryption/decryption operations.
    
    PLACEHOLDER IMPLEMENTATION with clear hooks for production:
    - Uses Fernet (symmetric encryption) as placeholder
    - In production: Integrate with AWS KMS or similar for key management
    - Implement envelope encryption (data key + master key)
    
    Attributes:
        master_key: Base64-encoded master key (from secure storage in prod)
        cipher: Fernet cipher instance
    """
    
    def __init__(self, master_key: str | None = None) -> None:
        """
        Initialize encryption manager.
        
        Args:
            master_key: Base64-encoded master key (generated if None)
        """
        if master_key is None:
            # PLACEHOLDER: In production, fetch from AWS KMS/Secrets Manager
            master_key = base64.urlsafe_b64encode(secrets.token_bytes(32)).decode()
            logger.warning(
                "Using generated master key (NOT SECURE FOR PRODUCTION)",
                extra={"action": "replace_with_kms"},
            )
        
        self.master_key = master_key
        self.cipher = Fernet(master_key.encode())
    
    def encrypt(self, plaintext: str | bytes) -> str:
        """
        Encrypt plaintext data.
        
        Args:
            plaintext: Data to encrypt (string or bytes)
            
        Returns:
            Base64-encoded encrypted data
            
        Example:
            encrypted = manager.encrypt("sensitive data")
        """
        try:
            if isinstance(plaintext, str):
                plaintext = plaintext.encode("utf-8")
            
            encrypted_bytes = self.cipher.encrypt(plaintext)
            encrypted_b64 = base64.b64encode(encrypted_bytes).decode("utf-8")
            
            logger.debug("Data encrypted", extra={"length": len(plaintext)})
            return encrypted_b64
        except Exception as e:
            logger.error(
                "Encryption failed",
                extra={"error": str(e)},
            )
            raise
    
    def decrypt(self, encrypted_data: str) -> str:
        """
        Decrypt encrypted data.
        
        Args:
            encrypted_data: Base64-encoded encrypted data
            
        Returns:
            Decrypted plaintext as string
            
        Raises:
            ValueError: If decryption fails (invalid data or key)
        """
        try:
            encrypted_bytes = base64.b64decode(encrypted_data.encode("utf-8"))
            decrypted_bytes = self.cipher.decrypt(encrypted_bytes)
            decrypted = decrypted_bytes.decode("utf-8")
            
            logger.debug("Data decrypted")
            return decrypted
        except Exception as e:
            logger.error(
                "Decryption failed",
                extra={"error": str(e)},
            )
            raise ValueError("Failed to decrypt data") from e
    
    @staticmethod
    def generate_key() -> str:
        """
        Generate a new Fernet key.
        
        Returns:
            Base64-encoded key
            
        Note: In production, use KMS to generate and manage keys
        """
        key = Fernet.generate_key()
        return key.decode("utf-8")
    
    @staticmethod
    def hash_data(data: str, salt: str | None = None) -> tuple[str, str]:
        """
        Hash data using PBKDF2-SHA256.
        
        Useful for hashing tokens, API keys before storage.
        
        Args:
            data: Data to hash
            salt: Salt (generated if None)
            
        Returns:
            Tuple of (hash, salt) as hex strings
        """
        if salt is None:
            salt = secrets.token_hex(32)
        
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt.encode("utf-8"),
            iterations=100000,
        )
        
        key = kdf.derive(data.encode("utf-8"))
        hash_hex = key.hex()
        
        return hash_hex, salt
    
    @staticmethod
    def verify_hash(data: str, hash_hex: str, salt: str) -> bool:
        """
        Verify data against a hash.
        
        Args:
            data: Original data
            hash_hex: Hash to verify against
            salt: Salt used for hashing
            
        Returns:
            True if data matches hash
        """
        computed_hash, _ = EncryptionManager.hash_data(data, salt)
        return secrets.compare_digest(computed_hash, hash_hex)


# Global encryption manager instance
_encryption_manager: EncryptionManager | None = None


def get_encryption_manager() -> EncryptionManager:
    """
    Get the global encryption manager instance.
    
    Returns:
        EncryptionManager instance
    """
    global _encryption_manager
    if _encryption_manager is None:
        _encryption_manager = EncryptionManager()
    return _encryption_manager


def configure_encryption(master_key: str | None = None) -> None:
    """
    Configure the global encryption manager.
    
    Args:
        master_key: Base64-encoded master key
    """
    global _encryption_manager
    _encryption_manager = EncryptionManager(master_key=master_key)
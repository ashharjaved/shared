"""
Password Service - Hashing and Verification
External adapter for password operations
"""
from __future__ import annotations

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError, InvalidHash

from shared.infrastructure.observability.logger import get_logger
from src.identity.domain.value_objects.password_hash import PasswordHash

logger = get_logger(__name__)


class PasswordService:
    """
    Password hashing service using Argon2id.
    
    Wrapper around domain PasswordHash value object for
    infrastructure-level password operations.
    """
    
    def __init__(self) -> None:
        """Initialize password service with Argon2 hasher"""
        self._hasher = PasswordHasher(
            time_cost=2,  # iterations
            memory_cost=65536,  # 64 MB
            parallelism=4,  # threads
            hash_len=32,  # output length
            salt_len=16,  # salt length
        )
    
    def hash_password(self, plain_password: str) -> PasswordHash:
        """
        Hash a plain text password.
        
        Args:
            plain_password: Plain text password
            
        Returns:
            PasswordHash value object
            
        Raises:
            ValueError: If password is too short
        """
        if len(plain_password) < 8:
            raise ValueError("Password must be at least 8 characters")
        
        return PasswordHash.from_plain_text(plain_password)
    
    def verify_password(
        self,
        plain_password: str,
        password_hash: PasswordHash,
    ) -> bool:
        """
        Verify a password against its hash.
        
        Args:
            plain_password: Plain text password
            password_hash: PasswordHash value object
            
        Returns:
            True if password matches, False otherwise
        """
        return password_hash.verify(plain_password)
    
    def needs_rehash(self, password_hash: PasswordHash) -> bool:
        """
        Check if hash needs updating due to new security parameters.
        
        Args:
            password_hash: PasswordHash value object
            
        Returns:
            True if rehash needed
        """
        return password_hash.needs_rehash()
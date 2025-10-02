"""
Password Hash Value Object
Handles Argon2id hashing and verification
"""
from __future__ import annotations

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError, InvalidHash

from shared.domain.base_value_object import BaseValueObject


class PasswordHash(BaseValueObject):
    """
    Password hash value object using Argon2id.
    
    Handles hashing and verification securely.
    Never stores plain text passwords.
    """
    
    _hasher = PasswordHasher(
        time_cost=2,  # iterations
        memory_cost=65536,  # 64 MB
        parallelism=4,  # threads
        hash_len=32,  # output length
        salt_len=16,  # salt length
    )
    
    def __init__(self, hashed_value: str) -> None:
        """
        Create from already-hashed password.
        
        Args:
            hashed_value: Argon2id hash string
        """
        self._value = hashed_value
        self._finalize_init()  # ← FIX: Enforce immutability
    
    @classmethod
    def from_plain_text(cls, plain_password: str) -> PasswordHash:
        """
        Hash a plain text password.
        
        Args:
            plain_password: Plain text password
            
        Returns:
            PasswordHash instance with hashed value
        """
        if len(plain_password) < 8:
            raise ValueError("Password must be at least 8 characters")
        
        hashed = cls._hasher.hash(plain_password)
        return cls(hashed)
    
    def verify(self, plain_password: str) -> bool:
        """
        Verify a plain text password against this hash.
        
        Args:
            plain_password: Plain text password to verify
            
        Returns:
            True if password matches, False otherwise
        """
        try:
            self._hasher.verify(self._value, plain_password)
            return True
        except (VerifyMismatchError, InvalidHash):
            return False
    
    def needs_rehash(self) -> bool:
        """Check if hash needs updating due to new security parameters"""
        return self._hasher.check_needs_rehash(self._value)
    
    @property
    def value(self) -> str:
        return self._value
    
    def __str__(self) -> str:
        return "[REDACTED]"  # Never expose hash
    
    def _get_equality_components(self) -> tuple:
        return (self._value,)
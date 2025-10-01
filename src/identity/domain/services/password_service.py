# src/identity/domain/services/password_service.py
from src.shared.security.passwords.ports import PasswordHasherPort
from src.identity.domain.value_objects.password_hash import PasswordHash 
from ..exception import ValidationError

class PasswordService:
    """Pure domain service for password operations."""

    MIN_PASSWORD_LENGTH = 8

    def __init__(self, hasher: PasswordHasherPort) -> None:
        self._hasher = hasher

    def hash_password(self, plain_password: str) -> PasswordHash:
        """
        Hash a plain text password and wrap it in a value object.
        """
        if not self._is_valid_password(plain_password):
            raise ValidationError("Password does not meet requirements")

        hashed_str = self._hasher.hash(plain_password)
        return PasswordHash.from_hash(hashed_str)

    def verify_password(self, plain_password: str, hashed: PasswordHash) -> bool:
        """
        Verify a plain password against a stored hash.
        """
        # IMPORTANT: use the raw stored value, not str(hashed) (which is "[REDACTED]")
        return self._hasher.verify(plain_password, hashed.value)

    def _is_valid_password(self, password: str) -> bool:
        """Validate password meets domain requirements."""
        if len(password) < self.MIN_PASSWORD_LENGTH:
            return False
        has_upper = any(c.isupper() for c in password)
        has_lower = any(c.islower() for c in password)
        has_digit = any(c.isdigit() for c in password)
        return has_upper and has_lower and has_digit

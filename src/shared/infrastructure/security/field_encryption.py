"""
Field-Level Encryption for Sensitive Data
Transparent encryption/decryption for ORM fields
"""
from __future__ import annotations

from typing import Any

from sqlalchemy import String, TypeDecorator

from shared.infrastructure.security.encryption import get_encryption_manager


class EncryptedString(TypeDecorator):
    """
    SQLAlchemy type decorator for transparent field encryption.
    
    Automatically encrypts data before writing to database and
    decrypts when reading from database.
    
    Usage in ORM model:
        from shared.infrastructure.security import EncryptedString
        from shared.infrastructure.database import Base
        from sqlalchemy import Column
        from uuid import UUID
        
        class User(Base):
            __tablename__ = "users"
            
            id: Mapped[UUID] = mapped_column(primary_key=True)
            email: Mapped[str] = mapped_column(String(255))
            ssn: Mapped[str | None] = mapped_column(EncryptedString(255), nullable=True)
            # SSN will be automatically encrypted/decrypted
            
            phone_encrypted: Mapped[str | None] = mapped_column(
                EncryptedString(255), 
                nullable=True
            )
            # Phone number stored encrypted
    
    Note:
        - In production, integrate with AWS KMS for key management
        - Current implementation uses Fernet (symmetric encryption)
        - Encrypted data takes more space than plaintext (base64 encoded)
    """
    
    impl = String
    cache_ok = True
    
    def process_bind_param(self, value: Any, dialect: Any) -> str | None:
        """
        Encrypt value before writing to database.
        
        This method is called when SQLAlchemy is preparing to insert/update
        a row in the database. It takes the Python value and converts it
        to the database representation (encrypted string).
        
        Args:
            value: Plain text value from Python object
            dialect: SQLAlchemy dialect (PostgreSQL, MySQL, etc.)
            
        Returns:
            Encrypted string (base64 encoded) or None if value is None
            
        Example:
            user.ssn = "123-45-6789"  # Plain text in Python
            # Stored as: "gAAAAABh..." (encrypted) in database
        """
        if value is None:
            return None
        
        # Get encryption manager
        manager = get_encryption_manager()
        
        # Encrypt the value
        encrypted = manager.encrypt(str(value))
        
        return encrypted
    
    def process_result_value(self, value: Any, dialect: Any) -> str | None:
        """
        Decrypt value after reading from database.
        
        This method is called when SQLAlchemy retrieves a row from the
        database. It takes the database representation (encrypted string)
        and converts it back to the Python value (plaintext).
        
        Args:
            value: Encrypted value from database
            dialect: SQLAlchemy dialect
            
        Returns:
            Decrypted string or None if value is None or decryption fails
            
        Example:
            # Database has: "gAAAAABh..." (encrypted)
            print(user.ssn)  # Prints: "123-45-6789" (decrypted)
        """
        if value is None:
            return None
        
        # Get encryption manager
        manager = get_encryption_manager()
        
        try:
            # Decrypt the value
            decrypted = manager.decrypt(value)
            return decrypted
        except Exception:
            # If decryption fails (corrupted data, wrong key, etc.)
            # Return None instead of raising exception
            # This prevents application crashes from corrupted data
            return None


class EncryptedText(TypeDecorator):
    """
    SQLAlchemy type decorator for encrypting TEXT fields.
    
    Similar to EncryptedString but for larger text fields.
    Use this for multi-line text, JSON strings, etc.
    
    Usage:
        from sqlalchemy import Text
        
        class Document(Base):
            __tablename__ = "documents"
            
            id: Mapped[UUID] = mapped_column(primary_key=True)
            sensitive_content: Mapped[str | None] = mapped_column(
                EncryptedText(),
                nullable=True
            )
    """
    
    impl = String
    cache_ok = True
    
    def process_bind_param(self, value: Any, dialect: Any) -> str | None:
        """Encrypt value before writing to database."""
        if value is None:
            return None
        
        manager = get_encryption_manager()
        return manager.encrypt(str(value))
    
    def process_result_value(self, value: Any, dialect: Any) -> str | None:
        """Decrypt value after reading from database."""
        if value is None:
            return None
        
        manager = get_encryption_manager()
        
        try:
            return manager.decrypt(value)
        except Exception:
            return None


class EncryptedJSON(TypeDecorator):
    """
    SQLAlchemy type decorator for encrypting JSON fields.
    
    Encrypts JSON data before storage and decrypts on retrieval.
    Useful for storing sensitive structured data.
    
    Usage:
        import json
        from sqlalchemy.dialects.postgresql import JSONB
        
        class UserProfile(Base):
            __tablename__ = "user_profiles"
            
            id: Mapped[UUID] = mapped_column(primary_key=True)
            medical_history: Mapped[dict | None] = mapped_column(
                EncryptedJSON(),
                nullable=True
            )
            
        # Usage:
        profile.medical_history = {
            "allergies": ["penicillin"],
            "conditions": ["diabetes"]
        }
        # Stored encrypted in database
    """
    
    impl = String
    cache_ok = True
    
    def process_bind_param(self, value: Any, dialect: Any) -> str | None:
        """Convert JSON to string, then encrypt."""
        if value is None:
            return None
        
        import json
        
        # Convert dict/list to JSON string
        json_str = json.dumps(value)
        
        # Encrypt the JSON string
        manager = get_encryption_manager()
        return manager.encrypt(json_str)
    
    def process_result_value(self, value: Any, dialect: Any) -> dict | list | None:
        """Decrypt, then parse JSON."""
        if value is None:
            return None
        
        import json
        
        manager = get_encryption_manager()
        
        try:
            # Decrypt the value
            decrypted = manager.decrypt(value)
            
            # Parse JSON
            return json.loads(decrypted)
        except Exception:
            # Return None on decryption or JSON parse failure
            return None


def encrypt_field_value(value: str) -> str:
    """
    Helper function to manually encrypt a field value.
    
    Useful when you need to encrypt values outside of ORM operations,
    such as in queries or business logic.
    
    Args:
        value: Plain text value to encrypt
        
    Returns:
        Encrypted string (base64 encoded)
        
    Example:
        encrypted_ssn = encrypt_field_value("123-45-6789")
        # Use in raw SQL or comparisons
    """
    manager = get_encryption_manager()
    return manager.encrypt(value)


def decrypt_field_value(encrypted_value: str) -> str:
    """
    Helper function to manually decrypt a field value.
    
    Args:
        encrypted_value: Encrypted string (base64 encoded)
        
    Returns:
        Decrypted plain text
        
    Raises:
        ValueError: If decryption fails
        
    Example:
        plain_ssn = decrypt_field_value(encrypted_value)
    """
    manager = get_encryption_manager()
    return manager.decrypt(encrypted_value)
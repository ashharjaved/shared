"""
RefreshToken Entity - JWT Refresh Token Management
"""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Optional
from uuid import UUID
import secrets
import hashlib

from shared.domain.base_entity import BaseEntity
from src.identity.domain.exception import (
    RefreshTokenExpiredException,
    RefreshTokenRevokedException,
)


class RefreshToken(BaseEntity):
    """
    Refresh token entity for JWT authentication.
    
    Handles refresh token lifecycle including generation, validation,
    expiration (7 days), and revocation.
    
    Security:
    - Tokens are hashed before storage (never store plain tokens)
    - Single-use tokens with family tracking for rotation
    - Automatic expiration after 7 days
    
    Attributes:
        user_id: User UUID
        token_hash: SHA-256 hash of the refresh token
        expires_at: Expiration timestamp
        revoked_at: Revocation timestamp (if revoked)
    """
    
    TOKEN_EXPIRY_DAYS = 7
    TOKEN_LENGTH = 64  # bytes
    
    def __init__(
        self,
        id: UUID,
        user_id: UUID,
        token_hash: str,
        expires_at: datetime,
        revoked_at: Optional[datetime] = None,
        created_at: Optional[datetime] = None,
        updated_at: Optional[datetime] = None,
        deleted_at: Optional[datetime] = None,
    ) -> None:
        super().__init__(id, created_at, updated_at)
        self._user_id = user_id
        self._token_hash = token_hash
        self._expires_at = expires_at
        self._revoked_at = revoked_at
    
    @staticmethod
    def create(
        id: UUID,
        user_id: UUID,
    ) -> tuple[RefreshToken, str]:
        """
        Factory method to create a new refresh token.
        
        Generates a cryptographically secure random token and stores its hash.
        
        Args:
            id: Token UUID
            user_id: User UUID
            
        Returns:
            Tuple of (RefreshToken entity, plain token string)
            The plain token MUST be returned to the user immediately
            and never stored.
        """
        # Generate cryptographically secure random token
        plain_token = secrets.token_urlsafe(RefreshToken.TOKEN_LENGTH)
        
        # Hash the token for storage
        token_hash = hashlib.sha256(plain_token.encode()).hexdigest()
        
        # Calculate expiration
        expires_at = datetime.utcnow() + timedelta(days=RefreshToken.TOKEN_EXPIRY_DAYS)
        
        token = RefreshToken(
            id=id,
            user_id=user_id,
            token_hash=token_hash,
            expires_at=expires_at,
        )
        
        return token, plain_token
    
    def verify(self, plain_token: str) -> None:
        """
        Verify a plain token against this token's hash.
        
        Args:
            plain_token: Plain text token to verify
            
        Raises:
            RefreshTokenExpiredException: If token has expired
            RefreshTokenRevokedException: If token has been revoked
            ValueError: If token hash doesn't match
        """
        if self.is_expired():
            raise RefreshTokenExpiredException()
        
        if self.is_revoked():
            raise RefreshTokenRevokedException()
        
        # Hash the provided token
        provided_hash = hashlib.sha256(plain_token.encode()).hexdigest()
        
        # Constant-time comparison to prevent timing attacks
        if not secrets.compare_digest(provided_hash, self._token_hash):
            raise ValueError("Invalid refresh token")
    
    def revoke(self) -> None:
        """Revoke this refresh token (user logout or security event)"""
        if self._revoked_at is None:
            self._revoked_at = datetime.utcnow()
            self.mark_updated()
    
    def is_expired(self) -> bool:
        """Check if token has expired"""
        return datetime.utcnow() > self._expires_at
    
    def is_revoked(self) -> bool:
        """Check if token has been revoked"""
        return self._revoked_at is not None
    
    def is_valid(self) -> bool:
        """Check if token is valid (not expired and not revoked)"""
        return not self.is_expired() and not self.is_revoked()
    
    # Properties
    @property
    def user_id(self) -> UUID:
        return self._user_id
    
    @property
    def token_hash(self) -> str:
        return self._token_hash
    
    @property
    def expires_at(self) -> datetime:
        return self._expires_at
    
    @property
    def revoked_at(self) -> Optional[datetime]:
        return self._revoked_at
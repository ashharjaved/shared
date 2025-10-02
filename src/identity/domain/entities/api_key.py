"""
ApiKey Entity - API Key Management for Programmatic Access
"""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Optional, Set
from uuid import UUID
import secrets
import hashlib

from shared.domain.base_entity import BaseEntity
from src.identity.domain.value_objects.permission import Permission
from src.identity.domain.exception import ApiKeyRevokedException, ApiKeyExpiredException


class ApiKey(BaseEntity):
    """
    API Key entity for programmatic access.
    
    Provides secure API key generation and management with:
    - Prefix-based identification (e.g., 'sk_live_abc123...')
    - Hashed storage (never store plain keys)
    - Permission scoping
    - Expiration and revocation
    - Usage tracking
    
    Attributes:
        organization_id: Organization UUID
        user_id: User who created the key (optional)
        name: Key name/description
        key_hash: SHA-256 hash of the API key
        key_prefix: Visible prefix for identification
        permissions: Set of granted permissions
        last_used_at: Last usage timestamp
        expires_at: Expiration timestamp (optional)
        is_active: Active status
        revoked_at: Revocation timestamp
    """
    
    KEY_LENGTH = 32  # bytes
    PREFIX_LENGTH = 8
    
    def __init__(
        self,
        id: UUID,
        organization_id: UUID,
        name: str,
        key_hash: str,
        key_prefix: str,
        user_id: Optional[UUID] = None,
        permissions: Optional[Set[Permission]] = None,
        last_used_at: Optional[datetime] = None,
        expires_at: Optional[datetime] = None,
        is_active: bool = True,
        revoked_at: Optional[datetime] = None,
        created_at: Optional[datetime] = None,
        updated_at: Optional[datetime] = None,
        deleted_at: Optional[datetime] = None,
    ) -> None:
        super().__init__(id, created_at, updated_at)
        self._organization_id = organization_id
        self._user_id = user_id
        self._name = name
        self._key_hash = key_hash
        self._key_prefix = key_prefix
        self._permissions = permissions or set()
        self._last_used_at = last_used_at
        self._expires_at = expires_at
        self._is_active = is_active
        self._revoked_at = revoked_at
    
    @staticmethod
    def create(
        id: UUID,
        organization_id: UUID,
        name: str,
        user_id: Optional[UUID] = None,
        permissions: Optional[Set[Permission]] = None,
        expires_in_days: Optional[int] = None,
    ) -> tuple[ApiKey, str]:
        """
        Factory method to create a new API key.
        
        Generates a cryptographically secure key with prefix.
        
        Args:
            id: API key UUID
            organization_id: Organization UUID
            name: Key name/description
            user_id: User who created the key
            permissions: Granted permissions
            expires_in_days: Expiration in days (None = never expires)
            
        Returns:
            Tuple of (ApiKey entity, plain key string)
            The plain key MUST be shown to user once and never stored.
        """
        # Generate random key
        random_bytes = secrets.token_bytes(ApiKey.KEY_LENGTH)
        plain_key = secrets.token_urlsafe(ApiKey.KEY_LENGTH)
        
        # Create prefix (first 8 chars of key for identification)
        key_prefix = f"sk_live_{plain_key[:ApiKey.PREFIX_LENGTH]}"
        
        # Hash the full key for storage
        key_hash = hashlib.sha256(plain_key.encode()).hexdigest()
        
        # Calculate expiration
        expires_at = None
        if expires_in_days:
            expires_at = datetime.utcnow() + timedelta(days=expires_in_days)
        
        api_key = ApiKey(
            id=id,
            organization_id=organization_id,
            user_id=user_id,
            name=name,
            key_hash=key_hash,
            key_prefix=key_prefix,
            permissions=permissions or set(),
            expires_at=expires_at,
            is_active=True,
        )
        
        # Return entity and plain key (to be shown once)
        full_key = f"{key_prefix}_{plain_key}"
        return api_key, full_key
    
    def verify(self, plain_key: str) -> None:
        """
        Verify a plain key against this key's hash.
        
        Args:
            plain_key: Plain API key to verify
            
        Raises:
            ApiKeyRevokedException: If key has been revoked
            ApiKeyExpiredException: If key has expired
            ValueError: If key hash doesn't match
        """
        if not self._is_active or self.is_revoked():
            raise ApiKeyRevokedException()
        
        if self.is_expired():
            raise ApiKeyExpiredException()
        
        # Extract the actual key (remove prefix)
        if "_" in plain_key:
            _, actual_key = plain_key.rsplit("_", 1)
        else:
            actual_key = plain_key
        
        # Hash and compare
        provided_hash = hashlib.sha256(actual_key.encode()).hexdigest()
        
        if not secrets.compare_digest(provided_hash, self._key_hash):
            raise ValueError("Invalid API key")
        
        # Update last used timestamp
        self._last_used_at = datetime.utcnow()
        self._touch()
    
    def revoke(self) -> None:
        """Revoke this API key"""
        if self._revoked_at is None:
            self._revoked_at = datetime.utcnow()
            self._is_active = False
            self._touch()
    
    def deactivate(self) -> None:
        """Temporarily deactivate (can be reactivated)"""
        self._is_active = False
        self._touch()
    
    def activate(self) -> None:
        """Reactivate a deactivated key"""
        if not self.is_revoked() and not self.is_expired():
            self._is_active = True
            self._touch()
    
    def is_expired(self) -> bool:
        """Check if key has expired"""
        if self._expires_at is None:
            return False
        return datetime.utcnow() > self._expires_at
    
    def is_revoked(self) -> bool:
        """Check if key has been revoked"""
        return self._revoked_at is not None
    
    def has_permission(self, permission: Permission) -> bool:
        """Check if key has a specific permission"""
        return permission in self._permissions
    
    # Properties
    @property
    def organization_id(self) -> UUID:
        return self._organization_id
    
    @property
    def user_id(self) -> Optional[UUID]:
        return self._user_id
    
    @property
    def name(self) -> str:
        return self._name
    
    @property
    def key_hash(self) -> str:
        return self._key_hash
    
    @property
    def key_prefix(self) -> str:
        return self._key_prefix
    
    @property
    def permissions(self) -> Set[Permission]:
        return self._permissions.copy()
    
    @property
    def last_used_at(self) -> Optional[datetime]:
        return self._last_used_at
    
    @property
    def expires_at(self) -> Optional[datetime]:
        return self._expires_at
    
    @property
    def is_active(self) -> bool:
        return self._is_active
    
    @property
    def revoked_at(self) -> Optional[datetime]:
        return self._revoked_at
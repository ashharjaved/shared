"""
JWT Service - Token Generation and Verification
External adapter for JWT operations
"""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Dict, Optional
from uuid import UUID

import jwt
from jwt.exceptions import ExpiredSignatureError, InvalidTokenError

from shared.infrastructure.observability.logger import get_logger

logger = get_logger(__name__)


class JWTService:
    """
    JWT token service for authentication.
    
    Handles access token and refresh token generation/verification.
    Uses HS256 algorithm with secret key.
    """
    
    # Token expiry times (from requirements)
    ACCESS_TOKEN_EXPIRY_MINUTES = 15
    REFRESH_TOKEN_EXPIRY_DAYS = 7
    
    def __init__(self, secret_key: str, algorithm: str = "HS256") -> None:
        """
        Initialize JWT service.
        
        Args:
            secret_key: Secret key for signing tokens
            algorithm: JWT algorithm (default: HS256)
        """
        self._secret_key = secret_key
        self._algorithm = algorithm
    
    def generate_access_token(
        self,
        user_id: UUID,
        organization_id: UUID,
        email: str,
        roles: list[str],
        permissions: list[str],
    ) -> str:
        """
        Generate JWT access token.
        
        Args:
            user_id: User UUID
            organization_id: Organization UUID
            email: User email
            roles: List of role names
            permissions: List of permission strings
            
        Returns:
            Encoded JWT token string
        """
        now = datetime.utcnow()
        expires_at = now + timedelta(minutes=self.ACCESS_TOKEN_EXPIRY_MINUTES)
        
        payload = {
            "sub": str(user_id),
            "org_id": str(organization_id),
            "email": email,
            "roles": roles,
            "permissions": permissions,
            "type": "access",
            "iat": now,
            "exp": expires_at,
        }
        
        token = jwt.encode(payload, self._secret_key, algorithm=self._algorithm)
        
        logger.debug(
            "Generated access token",
            extra={
                "user_id": str(user_id),
                "organization_id": str(organization_id),
                "expires_at": expires_at.isoformat(),
            },
        )
        
        return token
    
    def verify_access_token(self, token: str) -> Dict[str, Any]:
        """
        Verify and decode access token.
        
        Args:
            token: JWT token string
            
        Returns:
            Decoded token payload
            
        Raises:
            ExpiredSignatureError: If token has expired
            InvalidTokenError: If token is invalid
        """
        try:
            payload = jwt.decode(
                token,
                self._secret_key,
                algorithms=[self._algorithm],
            )
            
            # Verify token type
            if payload.get("type") != "access":
                raise InvalidTokenError("Invalid token type")
            
            return payload
            
        except ExpiredSignatureError:
            logger.warning("Access token expired", extra={"token": token[:20] + "..."})
            raise
        except InvalidTokenError as e:
            logger.warning(f"Invalid access token: {e}", extra={"token": token[:20] + "..."})
            raise
    
    def decode_token_without_verification(self, token: str) -> Optional[Dict[str, Any]]:
        """
        Decode token without verification (for inspection only).
        
        Args:
            token: JWT token string
            
        Returns:
            Decoded payload or None if invalid
        """
        try:
            return jwt.decode(
                token,
                options={"verify_signature": False},
            )
        except Exception as e:
            logger.error(f"Failed to decode token: {e}")
            return None
    
    def extract_user_id(self, token: str) -> Optional[UUID]:
        """
        Extract user ID from token without full verification.
        
        Useful for logging/debugging.
        
        Args:
            token: JWT token string
            
        Returns:
            User UUID or None
        """
        payload = self.decode_token_without_verification(token)
        if payload and "sub" in payload:
            try:
                return UUID(payload["sub"])
            except (ValueError, TypeError):
                return None
        return None
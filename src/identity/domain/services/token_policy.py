# src/identity/domain/services/token_policy.py

from dataclasses import dataclass
from datetime import timedelta
from typing import Dict, Set


@dataclass(frozen=True)
class TokenPolicy:
    """
    Domain rules and policies for JWT token management.
    
    Enforces token lifetime constraints, required claims,
    and security policies.
    """
    
    # Token Lifetimes (immutable domain rules)
    ACCESS_TOKEN_LIFETIME = timedelta(minutes=15)
    REFRESH_TOKEN_LIFETIME = timedelta(days=7)
    
    # Security constraints
    MIN_TOKEN_LENGTH = 32
    REQUIRED_ACCESS_CLAIMS: Set[str] = frozenset({
        "sub",        # Subject (user_id)
        "tenant_id",  # Tenant context
        "role",       # Primary role
        "exp",        # Expiration
        "iat",        # Issued at
        "type"        # Token type
    })
    
    REQUIRED_REFRESH_CLAIMS: Set[str] = frozenset({
        "sub",
        "tenant_id",
        "role",
        "exp",
        "iat",
        "type"
    })
    
    @staticmethod
    def validate_access_token_claims(claims: Dict) -> tuple[bool, str | None]:
        """
        Validate access token has all required claims.
        
        Args:
            claims: Decoded JWT claims dictionary
            
        Returns:
            (is_valid, error_message)
        """
        missing = TokenPolicy.REQUIRED_ACCESS_CLAIMS - set(claims.keys())
        
        if missing:
            return False, f"Missing required claims: {', '.join(missing)}"
        
        if claims.get("type") != "access":
            return False, "Invalid token type - expected 'access'"
        
        return True, None
    
    @staticmethod
    def validate_refresh_token_claims(claims: Dict) -> tuple[bool, str | None]:
        """
        Validate refresh token has all required claims.
        
        Args:
            claims: Decoded JWT claims dictionary
            
        Returns:
            (is_valid, error_message)
        """
        missing = TokenPolicy.REQUIRED_REFRESH_CLAIMS - set(claims.keys())
        
        if missing:
            return False, f"Missing required claims: {', '.join(missing)}"
        
        if claims.get("type") != "refresh":
            return False, "Invalid token type - expected 'refresh'"
        
        return True, None
    
    @staticmethod
    def is_access_token(claims: Dict) -> bool:
        """Check if claims represent an access token."""
        return claims.get("type") == "access"
    
    @staticmethod
    def is_refresh_token(claims: Dict) -> bool:
        """Check if claims represent a refresh token."""
        return claims.get("type") == "refresh"
    
    @staticmethod
    def extract_user_context(claims: Dict) -> tuple[str, str, str]:
        """
        Extract essential user context from token claims.
        
        Args:
            claims: Decoded JWT claims
            
        Returns:
            (user_id, tenant_id, role)
            
        Raises:
            ValueError: If required claims missing
        """
        try:
            return (
                claims["sub"],
                claims["tenant_id"],
                claims["role"]
            )
        except KeyError as e:
            raise ValueError(f"Missing required claim: {e}")
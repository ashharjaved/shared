# src/shared/security.py

import logging
from datetime import datetime, timedelta
from typing import Any, Dict, Optional, Union
from uuid import UUID
from cryptography.fernet import Fernet, InvalidToken
import os
import jwt
from passlib.context import CryptContext
from dotenv import load_dotenv 
from src.config import settings
from src.shared.exceptions import AuthenticationError

load_dotenv()
logger = logging.getLogger(__name__)

# Password hashing context - prefer Argon2id, fallback to bcrypt
try:
    pwd_context = CryptContext(
        schemes=["argon2", "bcrypt"],
        deprecated="auto",
        argon2__memory_cost=65536,
        argon2__time_cost=3,
        argon2__parallelism=4,
    )
except Exception as e:
    logger.warning(f"Argon2 not available, using bcrypt only: {e}")
    pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(plain_password: str) -> str:
    """
    Hash a plain text password using Argon2id (preferred) or bcrypt.
    
    Args:
        plain_password: The plain text password to hash
        
    Returns:
        The hashed password string
        
    Raises:
        ValueError: If password is empty or None
    """
    if not plain_password:
        raise ValueError("Password cannot be empty")
    
    return pwd_context.hash(plain_password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verify a plain text password against a hash.
    
    Args:
        plain_password: The plain text password to verify
        hashed_password: The stored password hash
        
    Returns:
        True if password matches, False otherwise
    """
    if not plain_password or not hashed_password:
        return False
    
    try:
        return pwd_context.verify(plain_password, hashed_password)
    except Exception as e:
        logger.error(f"Password verification error: {e}")
        return False

def _jwt_signing_key() -> Any:
    if settings.JWT_ALGORITHM == "RS256":
        return settings.JWT_PRIVATE_KEY
    return settings.JWT_SECRET

def _jwt_verify_key() -> Any:
    if settings.JWT_ALGORITHM == "RS256":
        return settings.JWT_PUBLIC_KEY
    return settings.JWT_SECRET

def create_access_token(
    sub: Union[str, UUID],
    tenant_id: UUID,
    role: str,
    expires_delta: Optional[timedelta] = None
) -> str:
    """
    Create a JWT access token with user claims.
    
    Args:
        sub: Subject (user ID)
        tenant_id: Tenant ID for the user
        role: User's role
        expires_delta: Token expiration time (defaults to config setting)
        
    Returns:
        Encoded JWT token string
    """
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode: Dict[str, Any] = {
        "sub": str(sub),
        "tenant_id": str(tenant_id),
        "role": role,
        "iat": int(datetime.utcnow().timestamp()),
        "exp": int(expire.timestamp()),
        "typ": "access",
    }    
    return jwt.encode(to_encode, _jwt_signing_key(), algorithm=settings.JWT_ALGORITHM)


def create_refresh_token(
    sub: Union[str, UUID],
    tenant_id: Union[str, UUID],
    role: str,
    expires_delta: Optional[timedelta] = None
) -> str:
    """
    Create a JWT refresh token.
    
    Args:
        sub: Subject (user ID)
        tenant_id: Tenant ID for the user
        expires_delta: Token expiration time (defaults to 7 days)
        
    Returns:
        Encoded JWT refresh token string
    """
    expire = datetime.utcnow() + (expires_delta or timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS))
    payload = {
        "sub": str(sub),
        "tenant_id": str(tenant_id),
        "role": role,
        "iat": int(datetime.utcnow().timestamp()),
        "exp": int(expire.timestamp()),
        "typ": "refresh",
    }
    return jwt.encode(payload, _jwt_signing_key(), algorithm=settings.JWT_ALGORITHM)


def decode_token(token: str) -> Dict[str, Any]:
    """
    Decode and verify a JWT token.
    
    Args:
        token: The JWT token string to decode
        
    Returns:
        Dictionary containing the token payload
        
    Raises:
        AuthenticationError: If token is invalid, expired, or malformed
    """
    try:
        return jwt.decode(token, _jwt_verify_key(), algorithms=[settings.JWT_ALGORITHM], options={"verify_exp": True})
    except jwt.ExpiredSignatureError:
        raise AuthenticationError("Token has expired")
    except jwt.InvalidTokenError as e:
        raise AuthenticationError(f"Invalid token: {e}")


def extract_user_id_from_token(token: str) -> UUID:
    """
    Extract user ID from a JWT token.
    
    Args:
        token: The JWT token string
        
    Returns:
        User ID as UUID
        
    Raises:
        AuthenticationError: If token is invalid or missing user ID
    """
    payload = decode_token(token)
    try:
        return UUID(payload["sub"])
    except (ValueError, KeyError):
        raise AuthenticationError("Invalid user ID in token")


def extract_tenant_id_from_token(token: str) -> UUID:
    """
    Extract tenant ID from a JWT token.
    
    Args:
        token: The JWT token string
        
    Returns:
        Tenant ID as UUID
        
    Raises:
        AuthenticationError: If token is invalid or missing tenant ID
    """
    payload = decode_token(token)
    try:
        return UUID(payload["tenant_id"])
    except (ValueError, KeyError):
        raise AuthenticationError("Invalid tenant ID in token")
    
def get_tenant_id_from_token(token: str) -> UUID:
    payload = decode_token(token)
    try:
        return UUID(payload["tenant_id"])
    except Exception:
        raise AuthenticationError("Invalid tenant_id in token")
    
_ENC_KEY = os.getenv("APP_ENCRYPTION_KEY")
if not _ENC_KEY:
    raise RuntimeError("APP_ENCRYPTION_KEY not set in environment")
_fernet = Fernet(_ENC_KEY.encode())

def get_encryptor():
    """
    Returns a callable that encrypts a string -> str (base64 encoded).
    Used for storing access tokens, webhook secrets, etc.
    """
    def _encrypt(plain: str) -> str:
        return _fernet.encrypt(plain.encode()).decode()
    return _encrypt


def get_decryptor():
    """
    Returns a callable that decrypts a string -> str (plaintext).
    Used for reading back sensitive values from DB.
    """
    def _decrypt(cipher: str) -> str:
        try:
            return _fernet.decrypt(cipher.encode()).decode()
        except InvalidToken:
            raise ValueError("Decryption failed – invalid key or corrupted data")
    return _decrypt
"""
User DTOs
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class UserDTO:
    """
    User Data Transfer Object.
    
    Used for passing user data between application layers.
    NOT used for API responses (use Pydantic schemas in API layer).
    """
    id: str
    organization_id: str
    email: str
    full_name: str
    is_active: bool
    email_verified: bool
    phone_verified: bool
    created_at: str
    phone: Optional[str] = None
    last_login_at: Optional[str] = None


@dataclass(frozen=True)
class UserListDTO:
    """
    Paginated user list DTO.
    """
    users: list[UserDTO]
    total: int
    skip: int
    limit: int
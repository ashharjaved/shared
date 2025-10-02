"""
Authentication DTOs
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class LoginResponseDTO:
    """
    Login response DTO containing JWT tokens and user info.
    """
    access_token: str
    refresh_token: str
    token_type: str
    expires_in: int  # seconds
    user_id: str
    organization_id: str
    email: str
    roles: list[str]
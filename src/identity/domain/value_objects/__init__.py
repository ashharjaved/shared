# src/identity/domain/value_objects/__init__.py
"""Value objects for the identity domain."""

from .email import Email
from .phone import Phone
from .role import Role
from .password_hash import PasswordHash
from .timestamps import Timestamps

__all__ = [
    'Email',
    'Phone', 
    'Role',
    'PasswordHash',
    'Timestamps',
]